from loguru import logger
import asyncio
import random
import cv2
import numpy as np
import os
import requests
from urllib.parse import urlparse

import base64

# 定义打码API (jfbym) 凭证 (需要用户供给，可设定到环境变量或在此硬编码)
JFBYM_TOKEN = os.getenv("JFBYM_TOKEN", "")

async def get_jfbym_gap(bg_buffer):
    """
    通过云端 jfbym 打码平台识别缺口
    """
    if not JFBYM_TOKEN:
         logger.info("   > ⚠️ [API] 未配置 JFBYM_TOKEN，无法调用云端识别引擎。")
         return 0
         
    logger.info("   > ☁️  正在将图片上传至云端打码平台解析...")
    try:
         b64_img = base64.b64encode(bg_buffer).decode('utf-8')
         payload = {
             "token": JFBYM_TOKEN, 
             "type": "20110", # 通用单图滑块
             "image": b64_img
         }
         
         # 异步请求，为求兼容，这里偷懒用 requests.post 配合 run_in_executor 或最简单的直接阻塞式（由于我们只需要等图）
         # 或者用 httpx 等异步库也可以。这里我们就暂时用同步 requests (受限环境可加包，此处省事直接调)
         resp = requests.post("http://api.jfbym.com/api/YmServer/customApi", json=payload, timeout=10)
         data = resp.json()
         
         if data.get("code") == 10000: # 成功码
             result_str = data.get("data", {}).get("data", "0")
             logger.info(f"   > ✅ 云打码返回缺口 X坐标={result_str}")
             return int(result_str)
         else:
             logger.info(f"   > ❌ 云端识别异常: {data}")
             return 0
             
    except Exception as e:
         logger.info(f"   > ❌ 连接打码平台出错: {e}")
         return 0

def generate_human_track(distance):
    """
    生成三段式拟真位移轨迹 (加速 -> 匀速 -> 减速 + 回弹微调)
    :param distance: 需要滑动的总距离 (像素)
    :return: List[int] 每一帧相对上一步滑动的像素点
    """
    track = []
    current = 0
    mid1 = distance * 0.3  # 加速阈值
    mid2 = distance * 0.8  # 减速阈值
    t = 0.2
    v = 0
    
    while current < distance:
        if current < mid1:
            a = random.randint(30, 40) # 加速度
        elif current < mid2:
            a = random.randint(10, 20) # 匀速波动
        else:
            a = -random.randint(20, 30) # 减速度
            
        v0 = v
        v = v0 + a * t
        move = v0 * t + 1 / 2 * a * t * t
        
        # 兜底：快到终点强行截断步长防止严重过冲
        if current + move > distance + random.randint(2, 5):
            move = distance - current + random.randint(1, 3)
            
        current += move
        track.append(round(move))

    # 加入过冲回弹
    overshoot = random.randint(2, 4)
    back_tracks = [-1] * overshoot
    track.extend(back_tracks)

    return track

def find_gap_local(bg_buffer):
    """
    基于 OpenCV 边缘检测与轮廓特征寻找缺口X坐标
    :param bg_buffer: 背景图字节流
    :return: 估计的缺口X坐标
    """
    import cv2
    import numpy as np
    
    np_img = np.frombuffer(bg_buffer, np.uint8)
    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 边缘检测
    edges = cv2.Canny(gray, 150, 450)
    
    # 查找所有外部轮廓
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_x = 0
    max_area = 0
    box_w, box_h = 50, 50 # 默认缺口大小估计
    
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cw * ch
        # 腾讯滑块通常是一个靠近正方形的区域，且不在最左侧区域 (x > 50)
        # 面积通常在 1000 到 6000 像素之间
        if 1000 < area < 8000 and 0.5 < cw/ch < 2.0 and x > 50:
            if area > max_area:
                max_area = area
                best_x = x
                box_w, box_h = cw, ch
                
    # 如果基于单一轮廓查不到，退回到局部的边缘像素密度扫描策略
    if best_x == 0:
        max_density = 0
        search_box_w, search_box_h = 45, 45
        for x in range(50, w - search_box_w, 2):
            # 通常缺口在中间部分
            for y in range(int(h * 0.2), int(h * 0.8) - search_box_h, 5):
                density = np.sum(edges[y:y+search_box_h, x:x+search_box_w]) / 255.0
                if density > max_density:
                    max_density = density
                    best_x = x
                    box_w, box_h = search_box_w, search_box_h

    # 调试输出：保存画了红框的背景图以便人工校验
    debug_img = image.copy()
    cv2.rectangle(debug_img, (best_x, int(h*0.2)), (best_x + box_w, int(h*0.8)), (0, 0, 255), 2)
    cv2.imwrite("debug_captcha_cv.png", debug_img)
    
    return best_x

async def perform_slide(page, frame, distance):
    """利用计算出的距离，驱动原生鼠标事件滑动"""
    # 必须从 page（顶层）定位滑块并获取屏幕绝对坐标系
    slider_btn = await frame.wait_for_selector('.tcaptcha-slider-button, #tcaptcha_drag_thumb, .tc-drag-thumb, #tcaptcha-drag-thumb', state="attached", timeout=5000)
    box = await slider_btn.bounding_box()
    if not box:
        return False

    center_x = box["x"] + box["width"] / 2
    center_y = box["y"] + box["height"] / 2
    
    # 1. 鼠标悬停并按下
    await page.mouse.move(center_x, center_y)
    await page.wait_for_timeout(random.randint(100, 300))
    await page.mouse.down()
    
    # 2. 生成轨迹并多段移动
    tracks = generate_human_track(distance)
    current_x = center_x
    current_y = center_y
    
    logger.info(f"📐 规划滑动总步数: {len(tracks)}，开始拖拽...")
    for index, t in enumerate(tracks):
        current_x += t
        # Y轴微小抖动
        dy = random.choice([-1, 0, 0, 0, 1])
        current_y += dy
        
        await page.mouse.move(current_x, current_y)
        # 施加段间延迟
        await page.wait_for_timeout(random.randint(15, 30))
        
        if (index + 1) % 5 == 0 or index == len(tracks) - 1:
            logger.info(f"   > 🐾 轨迹执行中... 步数: {index+1}/{len(tracks)}, 当前相对偏移: {current_x - center_x:.1f}px")
        
    await page.wait_for_timeout(random.randint(200, 400)) # 结束前暂作停顿
    await page.mouse.up()
    logger.info("✓ 物理滑动完毕")
    return True

async def solve_captcha_if_exists(page):
    """
    检查并解决腾讯沙箱验证码
    返回：True (无验证码或成功过图) | False (过图失败)
    """
    try:
        logger.info("   > 🛡️ [Captcha Check] 尝试侦测是否有安全校验证弹窗...")
        # 检测是否存在滑块 iframe
        iframe_el = await page.wait_for_selector('#tcaptcha_iframe', timeout=6000)
        if not iframe_el:
            logger.info("   > 🛡️ [Captcha Pass] 6秒内未侦测到滑块验证码，视作安全放行。")
            return True
            
        logger.info("   > 🛑 [Captcha Detected] 识别到腾讯沙箱验证码环境，准备规避 (Anti-Bot)")
        frame = await iframe_el.content_frame()
        
        # 修正：采用探针跑取出来的真实背景层和滑块按钮 ID
        # [DIV] id='slideBgWrap' class='tc-bg', 或者里面的 img
        bg_image_el = await frame.wait_for_selector('#slideBgWrap, #slideBg, .tc-bg', timeout=3000)
        # 截取弹窗中的原图背景 (等待渲染)
        await page.wait_for_timeout(2000) 
        bg_buffer = await bg_image_el.screenshot() 

        # 分析背景缺口坐标
        logger.info("   > 🧠 自研图像缺口匹配算法计算中...")
        gap_x = find_gap_local(bg_buffer)
        logger.info(f"   > 📍 图像逻辑估算缺口位置原始偏移值 X={gap_x}")
        
        # 计算滑动偏移量 (扣减按钮本身宽度的容差等)
        logger.info("   > 🔍 尝试通过在 Sandbox 内注入 JS 直接提取滑块与背景长宽尺寸...")
        # 为了防止被 Playwright 框架自身的特征检测阻断，放弃高级 DOM 类库而改用原生 DOM Api 拉取尺寸
        js_get_box = """
        () => {
            const btn = document.querySelector('.tcaptcha-slider-button, #tcaptcha_drag_thumb, .tc-drag-thumb, #tcaptcha-drag-thumb');
            const bg = document.querySelector('#slideBgWrap, #slideBg, .tc-bg');
            if(!btn || !bg) return null;
            const btnRect = btn.getBoundingClientRect();
            const bgRect = bg.getBoundingClientRect();
            return {
                btn_x: btnRect.x,
                bg_x: bgRect.x,
                bg_width: bgRect.width
            };
        }
        """
        box_info = await frame.evaluate(js_get_box)
        
        if not box_info:
             logger.info("   > ❌ [Captcha Error] JS注入获取滑块或背景的 ClientRect 失败，当前验证码不可响应或格式变更。")
             return False
             
        # 第一轮尝试使用本地 CV
        logger.info("   > 🧠 自研图像缺口匹配算法计算中...")
        gap_x = find_gap_local(bg_buffer)
        logger.info(f"   > 📍 图像逻辑估算缺口位置原始偏移值 X={gap_x}")
        
        # 抛弃 DOM Ratio 缩放。使用原始图片提取的X值直接减去原生图片上的按钮起始便宜
        # 另外我们还需注意：此处的 initial_offset 我们暂用 JS 读取的值 (通常btn也会跟图一起缩放，比例接近1)
        initial_offset = box_info["btn_x"] - box_info["bg_x"]
        slide_distance = gap_x - initial_offset - 8
        
        logger.info(f"   > 📏 本地CV无需缩放，需要托拽有效物理距离: {slide_distance:.2f}px")
        
        if slide_distance > 10 and slide_distance < box_info["bg_width"]:
             await perform_slide(page, frame, slide_distance)
             await page.wait_for_timeout(3000)
             
             still_visible = await page.locator('#tcaptcha_iframe').is_visible()
             if not still_visible:
                  logger.info("   > 🚀 TCaptcha 沙箱验证通过！(本地CV)")
                  return True
             else:
                  logger.warning("   > ❌ [Retry] 本地CV轨迹判定被风控拦截。正准备进行尝试或求救...")
        else:
             logger.warning("   > ⚠️ 阻断：本地CV估算距离极度违和")

        # 触发重试并启用云端兜底机制
        reload_btn = await frame.query_selector('#reload')
        if reload_btn:
            await reload_btn.click()
            await page.wait_for_timeout(3000) # 充分等待新图
            
            # 再抓一遍
            bg_image_el = await frame.wait_for_selector('#slideBgWrap, #slideBg, .tc-bg', timeout=3000)
            await page.wait_for_timeout(2000)
            bg_buffer = await bg_image_el.screenshot()
            
            box_info = await frame.evaluate(js_get_box)
            if not box_info:
                 return False
                 
            # 通过换算最新比例
            import cv2
            import numpy as np
            np_img = np.frombuffer(bg_buffer, np.uint8)
            img_mat = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
            img_width = img_mat.shape[1]
            scale_ratio = box_info["bg_width"] / float(img_width)
            
            # 走云端API
            cloud_gap_x = await get_jfbym_gap(bg_buffer)
            if cloud_gap_x > 0:
                 gap_x_scaled = cloud_gap_x * scale_ratio
                 initial_offset = box_info["btn_x"] - box_info["bg_x"]
                 slide_distance = gap_x_scaled - initial_offset - 8
                 logger.info(f"   > 📏 云打码修正后托拽有效物理距离: {slide_distance:.2f}px")
                 
                 await perform_slide(page, frame, slide_distance)
                 await page.wait_for_timeout(3000)
                 still_visible = await page.locator('#tcaptcha_iframe').is_visible()
                 if not still_visible:
                     logger.info("   > 🚀 TCaptcha 沙箱验证通过！(云端 API)")
                     return True

            logger.warning("   > ❌ TCaptcha 云端兜底后依然拦截。AI 路线计算全线崩溃。")
            return False
            
        logger.warning("   > ❌ 无法找到验证码重试刷新按钮。")
        return False
        
    except Exception as e:
        logger.info(f"   > ⭕ [Captcha Bypass] 页面安全校验模块触发静默退出 (或本身无需验证): Exception - {e}")
        return True # 未强迫弹出亦作放行
