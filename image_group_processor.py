import logging
import os

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("process.log"),
    logging.StreamHandler()
])
logger = logging.getLogger()

def create_image_folders(input_folder, output_base_folder):
    # 获取所有输入文件夹中的子文件夹
    for subfolder in os.listdir(input_folder):
        subfolder_path = os.path.join(input_folder, subfolder)
        if os.path.isdir(subfolder_path):
            tiff_folder = os.path.join(subfolder_path, 'tiff')
            if os.path.exists(tiff_folder):
                # 获取 tiff 文件夹中的所有 tiff 文件
                tiff_files = sorted([f for f in os.listdir(tiff_folder) if f.endswith('.tif')])

                # 遍历 tiff 文件，每八张图片为一组
                for i in range(0, len(tiff_files), 8):
                    group_name = os.path.splitext(tiff_files[i])[0][:-2]  # 获取文件名前缀，比如 'image_4325'
                    output_folder = os.path.join(output_base_folder, subfolder, group_name)

                    # 创建目标文件夹
                    os.makedirs(output_folder, exist_ok=True)
                    logger.info(f"Created folder: {output_folder}")

