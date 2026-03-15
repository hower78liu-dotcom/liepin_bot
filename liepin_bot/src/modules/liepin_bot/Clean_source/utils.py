import os
import shutil
import datetime
import logging

def setup_directories(output_dir):
    """确保输出目录及备份目录存在"""
    his_dir = os.path.join(output_dir, "HIS")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(his_dir, exist_ok=True)
    return his_dir

def handle_existing_output(output_file):
    """如果文件存在，添加时间戳移至 HIS 目录"""
    if not os.path.exists(output_file):
        return
        
    output_dir = os.path.dirname(output_file)
    his_dir = setup_directories(output_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(output_file)
    name, ext = os.path.splitext(basename)
    new_name = f"{name}_{timestamp}{ext}"
    his_path = os.path.join(his_dir, new_name)
    
    try:
        shutil.move(output_file, his_path)
        logging.info(f"Existing file moved to: {his_path}")
    except PermissionError:
        logging.error(f"Target file {output_file} is open by another program. Please close it.")
        raise
