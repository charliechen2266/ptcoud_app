import logging
import os
from pt_cloud_processor import PLYProcessor
from image_group_processor import create_image_folders
from params import prompt_user_for_input
from ui_modules import MainWindow
import sys
from PyQt5 import QtWidgets

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("process.log"),
    logging.StreamHandler()
])
logger = logging.getLogger()

if __name__ == "__main__":
    # 获取用户输入的参数，包括数据文件夹路径、输出文件夹路径以及四个数值
    inputs = prompt_user_for_input()
    if inputs:
        data_folder_path, output_folder_path, roi_radius, threshold, erosion_ratio, density_threshold = inputs

        # 处理所有子文件夹
        processor = PLYProcessor(roi_radius, threshold, erosion_ratio, density_threshold)
        processor.process_all_subfolders(data_folder_path, output_folder_path)

        # 设置 QApplication 以启动 GUI 应用
        app = QtWidgets.QApplication(sys.argv)

        # 设置 debug_folder\data_combitation 文件夹的路径
        root_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_folder', 'data_combitation')

        # 创建子文件夹结构
        create_image_folders(data_folder_path, root_folder)

        # 创建并显示主窗口
        main_window = MainWindow(root_folder, data_folder_path, output_folder_path)
        main_window.show()

        # 进入事件循环
        sys.exit(app.exec_())
    else:
        logger.info("用户取消了输入或未选择必要的文件夹。")
