import logging
from PyQt5 import QtWidgets,QtCore

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("process.log"),
    logging.StreamHandler()
])
logger = logging.getLogger()

class InputDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("输入参数")
        self.setLayout(QtWidgets.QVBoxLayout())

        # 创建并添加四个标签和输入框
        self.roi_radius_label = QtWidgets.QLabel("ROI 半径：")
        self.roi_radius_input = QtWidgets.QDoubleSpinBox()
        self.roi_radius_input.setRange(0.0000, 100.0)
        self.roi_radius_input.setDecimals(8)
        self.roi_radius_input.setValue(0.1)

        self.threshold_label = QtWidgets.QLabel("曲率阈值：")
        self.threshold_input = QtWidgets.QDoubleSpinBox()
        self.threshold_input.setRange(0.0001, 1.0)
        self.threshold_input.setDecimals(8)
        self.threshold_input.setValue(0.1)

        self.erosion_ratio_label = QtWidgets.QLabel("侵蚀比：")
        self.erosion_ratio_input = QtWidgets.QDoubleSpinBox()
        self.erosion_ratio_input.setRange(0.0000, 1.0)
        self.erosion_ratio_input.setDecimals(8)
        self.erosion_ratio_input.setValue(0.10)

        self.density_threshold_label = QtWidgets.QLabel("密度阈值：")
        self.density_threshold_input = QtWidgets.QDoubleSpinBox()
        self.density_threshold_input.setRange(0.0000, 1.0)
        self.density_threshold_input.setDecimals(8)
        self.density_threshold_input.setValue(0.1)

        # 将输入框添加到布局中
        self.layout().addWidget(self.roi_radius_label)
        self.layout().addWidget(self.roi_radius_input)
        self.layout().addWidget(self.threshold_label)
        self.layout().addWidget(self.threshold_input)
        self.layout().addWidget(self.erosion_ratio_label)
        self.layout().addWidget(self.erosion_ratio_input)
        self.layout().addWidget(self.density_threshold_label)
        self.layout().addWidget(self.density_threshold_input)

        # 添加确定和取消按钮
        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout().addWidget(self.button_box)

    def getValues(self):
        return (self.roi_radius_input.value(), self.threshold_input.value(),
                self.erosion_ratio_input.value(), self.density_threshold_input.value())

def prompt_user_for_input():
    """弹出对话框获取用户输入"""
    app = QtWidgets.QApplication([])
    data_folder_path = QtWidgets.QFileDialog.getExistingDirectory(None, "选择数据文件夹")
    output_folder_path = QtWidgets.QFileDialog.getExistingDirectory(None, "选择输出文件夹")

    if not data_folder_path or not output_folder_path:
        logger.error("未选择数据文件夹或输出文件夹")
        return None

    dialog = InputDialog()
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return data_folder_path, output_folder_path, *dialog.getValues()
    else:
        return None
