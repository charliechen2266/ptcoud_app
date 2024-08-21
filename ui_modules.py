import logging
import os
import re
import shutil
import sys
import cv2
import open3d as o3d
from PyQt5 import QtWidgets, QtGui, QtCore
import ctypes

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("process.log"),
    logging.StreamHandler()
])
logger = logging.getLogger()



class ExposureDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置曝光检测参数")

        # 创建布局
        layout = QtWidgets.QFormLayout(self)

        # 创建输入字段
        self.exposure_threshold_input = QtWidgets.QLineEdit(self)
        self.exposure_threshold_input.setValidator(QtGui.QIntValidator(0, 255, self))

        self.continuous_pixel_count_input = QtWidgets.QLineEdit(self)
        self.continuous_pixel_count_input.setValidator(QtGui.QIntValidator(1, 100, self))

        self.max_exposure_count_input = QtWidgets.QLineEdit(self)
        self.max_exposure_count_input.setValidator(QtGui.QIntValidator(0, 1000, self))

        # 将输入字段添加到布局
        layout.addRow("曝光阈值:", self.exposure_threshold_input)
        layout.addRow("连续像素数要求:", self.continuous_pixel_count_input)
        layout.addRow("最大曝光组数:", self.max_exposure_count_input)

        # 添加按钮
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def get_values(self):
        return {
            "exposure_threshold": int(self.exposure_threshold_input.text()),
            "continuous_pixel_count": int(self.continuous_pixel_count_input.text()),
            "max_exposure_count": int(self.max_exposure_count_input.text())
        }


class ImageDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.missing_ply_group_names = set()
        self.overexposed_group_names = set()
        logger.info("ImageDelegate 初始化完成")

    def set_missing_ply_group_names(self, missing_ply_group_names):
        self.missing_ply_group_names.update(missing_ply_group_names)
        logger.info(f"缺失 PLY 组名称已更新: {self.missing_ply_group_names}")

    def set_overexposed_group_names(self, overexposed_group_names):
        self.overexposed_group_names.update(overexposed_group_names)
        logger.info(f"过曝组名称已更新: {self.overexposed_group_names}")

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        style = QtWidgets.QApplication.style()
        if index.isValid():
            item_text = index.data(QtCore.Qt.DisplayRole)

            if item_text:
                # 检查警告图标绘制

                if any(item_text in group_name for group_name in self.missing_ply_group_names):
                    alert_icon = style.standardIcon(QtWidgets.QStyle.SP_BrowserStop)
                    alert_icon.paint(painter, option.rect.adjusted(option.rect.width() - 20, 0, 50, 0))
                    logger.info(
                        f"绘制警告图标于: {item_text} (位置: {option.rect.adjusted(option.rect.width() - 20, 0, 50, 0)})")

                # 检查曝光图标绘制
                else:
                    if any(item_text in group_name for group_name in self.overexposed_group_names):
                        exposure_icon = style.standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning)
                        exposure_icon.paint(painter, option.rect.adjusted(option.rect.width() - 40, 0, 50, 0))
                        logger.info(
                            f"绘制曝光图标于: {item_text} (位置: {option.rect.adjusted(option.rect.width() - 40, 0, 50, 0)})")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, root_folder, input_folder, output_folder):
        super().__init__()
        self.setWindowTitle("Data Combitation Viewer")

        self.input_folder = input_folder
        self.output_folder = output_folder

        # 创建主Widget
        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)

        # 创建主布局
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)

        # 创建水平布局来包含tree_view和图片
        self.horizontal_layout = QtWidgets.QHBoxLayout()

        # 创建QTreeView来显示文件夹
        self.tree_view = QtWidgets.QTreeView()
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath(root_folder)
        self.tree_view.setModel(self.model)
        self.tree_view.setRootIndex(self.model.index(root_folder))
        self.tree_view.setHeaderHidden(True)

        # 设置列宽以适应文件夹名称
        header = self.tree_view.header()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        # 初始化 ImageDelegate，不再传入路径
        self.delegate = ImageDelegate()
        self.tree_view.setItemDelegate(self.delegate)
        self.tree_view.clicked.connect(self.on_tree_view_clicked)

        # 创建显示图片的布局
        self.image_layout = QtWidgets.QGridLayout()
        self.image_labels = [QtWidgets.QLabel(self) for _ in range(8)]
        for i, label in enumerate(self.image_labels):
            label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.image_layout.addWidget(label, i // 2, i % 2)

        # 创建菜单栏
        menubar = self.menuBar()

        # 添加“文件”菜单
        file_menu = menubar.addMenu('文件')
        self.create_menu_action(file_menu, '输出所有过曝组的照片', self.output_exposure_photos)
        self.create_menu_action(file_menu, '输出缺少 PLY 文件的图片组', self.output_missing_ply_photos)

        # 添加“视图”菜单
        view_menu = menubar.addMenu('视图')
        self.create_menu_action(view_menu, '切换显示模式', self.toggle_mode)
        self.create_menu_action(view_menu, '检测图像中的过曝情况', self.detect_exposure)

        # 创建工具栏
        self.toolbar = QtWidgets.QToolBar()
        self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolbar)

        # 创建切换模式按钮
        self.mode_button = QtWidgets.QPushButton()
        self.mode_button.setFixedSize(40, 40)
        self.mode_button.setStyleSheet("QPushButton { border: none; }")
        self.current_mode = "point_cloud"  # 初始为点云模式
        self.current_color_mode = "original"  # 初始为原始模式
        self.update_mode_icon()  # 初始时设置图标
        self.mode_button.setToolTip("切换显示模式")
        self.mode_button.clicked.connect(self.toggle_mode)
        self.toolbar.addWidget(self.mode_button)

        # 添加曝光检测按钮
        self.exposure_button = QtWidgets.QPushButton()
        self.exposure_button.setFixedSize(40, 40)
        self.exposure_button.setIcon(
            QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        self.exposure_button.setIconSize(QtCore.QSize(40, 40))
        self.exposure_button.setStyleSheet("QPushButton { border: none; }")
        self.exposure_button.setToolTip("检测图像中的过曝情况")
        self.exposure_button.clicked.connect(self.detect_exposure)
        self.toolbar.addWidget(self.exposure_button)

        # 添加输出过曝组照片按钮
        self.output_exposure_button = QtWidgets.QPushButton()
        self.output_exposure_button.setFixedSize(40, 40)
        self.output_exposure_button.setIcon(
            QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        self.output_exposure_button.setIconSize(QtCore.QSize(40, 40))
        self.output_exposure_button.setStyleSheet("QPushButton { border: none; }")
        self.output_exposure_button.setToolTip("输出所有过曝组的照片")
        self.output_exposure_button.clicked.connect(self.output_exposure_photos)
        self.toolbar.addWidget(self.output_exposure_button)

        # 创建输出缺少 PLY 文件组的按钮
        self.output_missing_ply_button = QtWidgets.QPushButton()
        self.output_missing_ply_button.setFixedSize(40, 40)
        self.output_missing_ply_button.setIcon(
            QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogOkButton))
        self.output_missing_ply_button.setIconSize(QtCore.QSize(40, 40))
        self.output_missing_ply_button.setStyleSheet("QPushButton { border: none; }")
        self.output_missing_ply_button.setToolTip("输出缺少 PLY 文件的图片组")
        self.output_missing_ply_button.clicked.connect(self.output_missing_ply_photos)
        self.toolbar.addWidget(self.output_missing_ply_button)

        # 将tree_view和image_layout添加到水平布局中
        self.horizontal_layout.addWidget(self.tree_view)
        self.horizontal_layout.addLayout(self.image_layout)

        # 将水平布局添加到主布局中
        self.main_layout.addLayout(self.horizontal_layout)

        # 初始化Open3D显示窗口
        self.init_open3d_windows()

        # 延迟调整窗口位置
        QtCore.QTimer.singleShot(100, self.adjust_open3d_windows_position)

        # 当前选择的文件夹路径
        self.current_group = None

        # 调整窗口大小
        self.setGeometry(100, 80, 1000, 800)

    def create_menu_action(self, menu, text, slot):
        action = QtWidgets.QAction(text, self)
        action.triggered.connect(slot)
        menu.addAction(action)

    # 曝光检测函数
    def detect_exposure(self):
        dialog = ExposureDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # 获取用户输入的值
            values = dialog.get_values()

            exposure_threshold = values["exposure_threshold"]
            continuous_pixel_count = values["continuous_pixel_count"]
            max_exposure_count = values["max_exposure_count"]

            if self.current_group:
                # 打印当前组信息
                logger.info(f"当前组: {self.current_group}")

                # 计算相对路径
                relative_path = os.path.relpath(self.current_group,
                                                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_folder',
                                                             'data_combitation'))
                logger.info(f"相对路径: {relative_path}")

                # 构造 base_folder 路径
                base_folder = os.path.join(self.input_folder, relative_path.split(os.sep)[0])
                logger.info(f"基础文件夹: {base_folder}")

                # 构造 tiff 文件夹路径
                tiff_folder_path = os.path.join(base_folder, "tiff")
                logger.info(f"TIFF 文件夹路径: {tiff_folder_path}")

                if os.path.exists(tiff_folder_path):
                    # 列出 TIFF 文件并排序
                    tiff_files = sorted([f for f in os.listdir(tiff_folder_path) if f.endswith('.tif')])
                    logger.info(f"找到的 TIFF 文件: {tiff_files}")

                    # 检查曝光情况
                    overexposed_images = self.check_exposure(tiff_files, tiff_folder_path, exposure_threshold,
                                                             continuous_pixel_count, max_exposure_count)
                    logger.info(f"过曝图像: {overexposed_images}")

                    # 标记过曝图像
                    self.mark_overexposed_nodes(overexposed_images)
                    logger.info("过曝图像已标记")
                else:
                    logger.warning("TIFF 文件夹不存在")

    def check_exposure(self, tiff_files, tiff_folder_path, exposure_threshold, continuous_pixel_count,
                       max_exposure_count):
        overexposed_images = []
        logger.info("开始曝光检查。")
        logger.info(f"曝光阈值: {exposure_threshold}")
        logger.info(f"连续像素数要求: {continuous_pixel_count}")
        logger.info(f"最大曝光组数: {max_exposure_count}")

        # 统计每个组的总曝光数
        group_exposure_count = {}

        for tiff_file in tiff_files:
            # 提取文件的索引部分（如 image_54_3.tif 中的 "3"）
            index_str = os.path.splitext(tiff_file)[0].split('_')[-1]

            # 仅处理索引在 3 到 6 之间的文件
            if index_str.isdigit() and 3 <= int(index_str) <= 6:
                image_path = os.path.join(tiff_folder_path, tiff_file)
                logger.info(f"正在处理文件: {tiff_file}")

                image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

                if image is None:
                    logger.error(f"无法读取图像: {tiff_file}")
                    continue

                # 应用阈值以找到过曝像素
                _, thresholded = cv2.threshold(image, exposure_threshold, 255, cv2.THRESH_BINARY)
                logger.info(f"已计算阈值图像: {tiff_file}")

                # 统计当前文件的过曝像素数
                total_overexposure_count = 0
                for row_idx, row in enumerate(thresholded):
                    consecutive_count = 0
                    for pixel in row:
                        if pixel >= exposure_threshold:
                            consecutive_count += 1
                            if consecutive_count >= continuous_pixel_count:
                                total_overexposure_count += 1
                                break
                        else:
                            consecutive_count = 0
                    if row_idx % 79 == 0:  # 每处理80行输出一次信息
                        logger.info(f"已处理 {tiff_file} 的第 {row_idx} 行")

                # 记录每个组的总曝光数
                group_name = os.path.splitext(tiff_file)[0][:-2]  # 提取组名
                if group_name not in group_exposure_count:
                    group_exposure_count[group_name] = 0
                group_exposure_count[group_name] += total_overexposure_count

                logger.info(f"文件 {tiff_file} 检测到过曝，组数: {total_overexposure_count}")
            else:
                logger.info(f"跳过文件: {tiff_file}")

        # 确定过曝的组
        for group_name, total_count in group_exposure_count.items():
            if total_count >= max_exposure_count:
                overexposed_images.append(group_name)
                logger.info(f"组 {group_name} 总曝光数 {total_count} 超过最大值 {max_exposure_count}")

        logger.info(f"曝光检查完成, 返回过曝文件 {overexposed_images}")
        return overexposed_images

    def mark_overexposed_nodes(self, overexposed_images):
        # 打印过曝图像列表
        logger.info("过曝图像列表:", overexposed_images)

        # 调用代理设置过曝组名称
        self.delegate.set_overexposed_group_names(overexposed_images)

        # 调试: 确认更新视图的调用
        logger.info("更新树视图")

        # 更新树视图
        self.tree_view.viewport().update()

        # 确认更新已完成
        logger.info("树视图更新完成")

    def init_open3d_windows(self):
        self.viewer1 = o3d.visualization.Visualizer()
        self.viewer1.create_window(window_name='PLY Viewer 1')

        self.viewer2 = o3d.visualization.Visualizer()
        self.viewer2.create_window(window_name='PLY Viewer 2')


    def adjust_open3d_windows_position(self):
        # 获取窗口句柄
        hwnd1 = self.get_window_handle("PLY Viewer 1")
        hwnd2 = self.get_window_handle("PLY Viewer 2")

        if hwnd1:
            ctypes.windll.user32.SetWindowPos(hwnd1, 0, 1300, 100, 550, 400, 0)  # 更改位置 (100, 100)
        if hwnd2:
            ctypes.windll.user32.SetWindowPos(hwnd2, 0, 1300, 500, 550, 400, 0)  # 更改位置 (750, 100)

    def get_window_handle(self, window_name):
        hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
        return hwnd if hwnd else None

    def on_tree_view_clicked(self, index):
        # 获取树状图点击的路径
        path = self.model.filePath(index)

        if os.path.isdir(path):
            self.current_group = path  # 记录当前选择的文件夹路径
            self.update_images_and_ply_files()

    def update_images_and_ply_files(self):
        if self.current_group:
            # 根据当前选择的路径生成相应的输入和输出文件夹路径
            relative_path = os.path.relpath(self.current_group,
                                            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_folder',
                                                         'data_combitation'))
            base_folder = os.path.join(self.input_folder, relative_path.split(os.sep)[0])
            output_folder = os.path.join(self.output_folder, relative_path.split(os.sep)[0])

            # 更新图片
            self.load_images(base_folder, relative_path.split(os.sep)[-1])

            # 更新PLY文件
            self.update_ply_files(output_folder)

            # 设置警告图片
            self.set_alert_images()

    def set_alert_images(self):
        missing_ply_group_names = set()

        if self.current_group:
            relative_path = os.path.relpath(self.current_group,
                                            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_folder',
                                                         'data_combitation'))
            base_folder = os.path.join(self.input_folder, relative_path.split(os.sep)[0])
            tiff_folder_path = os.path.join(base_folder, "tiff")

            if os.path.exists(tiff_folder_path):
                # 提取所有组名
                group_names = {os.path.splitext(f)[0][:-2] for f in sorted(os.listdir(tiff_folder_path)) if
                               f.endswith('.tif')}

                for group_name in group_names:
                    output_folder = os.path.join(self.output_folder, relative_path.split(os.sep)[0])

                    # 对每个组，检查是否缺少对应的 .ply 文件
                    expected_ply_file = f"{group_name}.ply"
                    if not os.path.exists(output_folder) or not os.path.exists(
                            os.path.join(output_folder, expected_ply_file)):
                        missing_ply_group_names.add(group_name)

        # 设置缺少 PLY 文件的组名
        self.delegate.set_missing_ply_group_names(missing_ply_group_names)
        self.tree_view.viewport().update()

    def load_images(self, base_folder, group_name):
        tiff_folder_path = os.path.join(base_folder, "tiff")
        if os.path.exists(tiff_folder_path):
            tiff_files = [f for f in sorted(os.listdir(tiff_folder_path)) if
                          f.startswith(group_name) and f.endswith('.tif')]

            # 按照指定顺序显示图片
            display_order = [7, 3, 0, 4, 1, 5, 2, 6]  # 你想要的图片显示顺序

            for i, index in enumerate(display_order):
                if index < len(tiff_files):
                    image_path = os.path.join(tiff_folder_path, tiff_files[index])
                    pixmap = QtGui.QPixmap(image_path)
                    if pixmap.isNull():
                        logger.error(f"Failed to load image: {image_path}")
                    else:
                        self.image_labels[i].setPixmap(
                            pixmap.scaled(self.image_labels[i].size(), QtCore.Qt.KeepAspectRatio,
                                          QtCore.Qt.SmoothTransformation))
                else:
                    self.image_labels[i].clear()  # 清除多余的label
        else:
            logger.warning(f"TIFF文件夹不存在: {tiff_folder_path}")

    def update_ply_files(self, output_folder):
        # 清除现有几何体
        self.viewer1.clear_geometries()
        self.viewer2.clear_geometries()

        # 根据当前模式和颜色模式选择PLY文件
        file_types = {
            "point_cloud_colored": r"^{}\.ply$".format(os.path.basename(self.current_group)),
            "point_cloud_original": r"^{}_colored\.ply$".format(os.path.basename(self.current_group)),
            "mesh_original": r"^{}_colored_colored_filtered_mesh\.ply$".format(os.path.basename(self.current_group)),
            "mesh_colored": r"^{}_original_filtered_mesh\.ply$".format(os.path.basename(self.current_group))
        }

        if self.current_mode == "point_cloud":
            if self.current_color_mode == "original":
                file_pattern1 = file_types["point_cloud_original"]
                file_pattern2 = file_types["point_cloud_colored"]
            else:
                file_pattern1 = file_types["point_cloud_colored"]
                file_pattern2 = file_types["point_cloud_original"]
        else:
            if self.current_color_mode == "original":
                file_pattern1 = file_types["mesh_original"]
                file_pattern2 = file_types["mesh_colored"]
            else:
                file_pattern1 = file_types["mesh_colored"]
                file_pattern2 = file_types["mesh_original"]

        ply_files1 = [f for f in sorted(os.listdir(output_folder)) if re.match(file_pattern1, f)]
        ply_files2 = [f for f in sorted(os.listdir(output_folder)) if re.match(file_pattern2, f)]

        for ply_file in ply_files1:
            ply_file_path = os.path.join(output_folder, ply_file)
            if "mesh" in ply_file:
                mesh = o3d.io.read_triangle_mesh(ply_file_path)
                if not mesh.is_empty():
                    self.viewer1.add_geometry(mesh)
                else:
                    logger.error(f"Failed to load mesh in viewer 1: {ply_file_path}")
            else:
                pcd = o3d.io.read_point_cloud(ply_file_path)
                if not pcd.is_empty():
                    self.viewer1.add_geometry(pcd)
                else:
                    logger.error(f"Failed to load point cloud in viewer 1: {ply_file_path}")

        for ply_file in ply_files2:
            ply_file_path = os.path.join(output_folder, ply_file)
            if "mesh" in ply_file:
                mesh = o3d.io.read_triangle_mesh(ply_file_path)
                if not mesh.is_empty():
                    self.viewer2.add_geometry(mesh)
                else:
                    logger.error(f"Failed to load mesh in viewer 2: {ply_file_path}")
            else:
                pcd = o3d.io.read_point_cloud(ply_file_path)
                if not pcd.is_empty():
                    self.viewer2.add_geometry(pcd)
                else:
                    logger.error(f"Failed to load point cloud in viewer 2: {ply_file_path}")

        self.viewer1.poll_events()
        self.viewer1.update_renderer()
        self.viewer2.poll_events()
        self.viewer2.update_renderer()

    def update_mode_icon(self):
        style = self.style()
        if self.current_mode == "point_cloud":
            self.mode_button.setIcon(style.standardIcon(QtWidgets.QStyle.SP_ArrowRight))
            self.mode_button.setToolTip("切换到网格模式")
        else:
            self.mode_button.setIcon(style.standardIcon(QtWidgets.QStyle.SP_ArrowLeft))
            self.mode_button.setToolTip("切换到点云模式")

    def toggle_mode(self):
        if self.current_mode == "point_cloud":
            self.current_mode = "mesh"
        else:
            self.current_mode = "point_cloud"

        self.update_mode_icon()  # 更新图标和提示信息

        if self.current_group:
            self.update_ply_files(os.path.join(self.output_folder, os.path.relpath(self.current_group, os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'debug_folder', 'data_combitation')).split(os.sep)[0]))

    def output_exposure_photos(self):
        # 获取过曝组名称
        overexposed_groups = self.delegate.overexposed_group_names

        if not overexposed_groups:
            logger.warning("没有过曝组")
            return

        # 获取当前文件的根目录
        root_directory = os.path.dirname(os.path.abspath(__file__))

        # 创建输出目录
        output_folder = os.path.join(root_directory, 'output_exposure_photos')
        os.makedirs(output_folder, exist_ok=True)

        # 遍历每个过曝组
        for group_name in overexposed_groups:
            # 遍历 input_folder 下的所有文件夹
            for folder in os.listdir(self.input_folder):
                tiff_folder_path = os.path.join(self.input_folder, folder, "tiff")
                if os.path.exists(tiff_folder_path):
                    # 获取该 TIFF 文件夹下的所有 TIFF 文件
                    tiff_files = [f for f in sorted(os.listdir(tiff_folder_path)) if f.endswith('.tif')]

                    # 找到属于当前过曝组的文件
                    for tiff_file in tiff_files:
                        if tiff_file.startswith(group_name):
                            # 生成输出文件夹路径，保持与输入路径一致
                            group_output_folder = os.path.join(output_folder, folder, "tiff")
                            os.makedirs(group_output_folder, exist_ok=True)

                            # 复制文件到输出文件夹
                            src_file = os.path.join(tiff_folder_path, tiff_file)
                            dest_file = os.path.join(group_output_folder, tiff_file)
                            shutil.copy2(src_file, dest_file)

                            logger.info(f"复制过曝文件: {tiff_file} 到 {group_output_folder}")
                else:
                    logger.warning(f"TIFF 文件夹不存在: {tiff_folder_path}")

        logger.info("所有过曝组的照片已输出完毕")

    def output_missing_ply_photos(self):
        # 获取缺少 PLY 文件的组名称
        missing_ply_groups = self.delegate.missing_ply_group_names

        if not missing_ply_groups:
            logger.warning("没有缺少 PLY 文件的组")
            return

        # 获取当前文件的根目录
        root_directory = os.path.dirname(os.path.abspath(__file__))

        # 创建输出目录
        output_folder = os.path.join(root_directory, 'output_missing_ply_photos')
        os.makedirs(output_folder, exist_ok=True)

        # 遍历每个缺少 PLY 文件的组
        for group_name in missing_ply_groups:
            # 遍历 input_folder 下的所有文件夹
            for folder in os.listdir(self.input_folder):
                tiff_folder_path = os.path.join(self.input_folder, folder, "tiff")
                if os.path.exists(tiff_folder_path):
                    # 获取该 TIFF 文件夹下的所有 TIFF 文件
                    tiff_files = [f for f in sorted(os.listdir(tiff_folder_path)) if f.endswith('.tif')]

                    # 找到属于当前缺少 PLY 文件组的文件
                    for tiff_file in tiff_files:
                        if tiff_file.startswith(group_name):
                            # 生成输出文件夹路径，保持与输入路径一致
                            group_output_folder = os.path.join(output_folder, folder, "tiff")
                            os.makedirs(group_output_folder, exist_ok=True)

                            # 复制文件到输出文件夹
                            src_file = os.path.join(tiff_folder_path, tiff_file)
                            dest_file = os.path.join(group_output_folder, tiff_file)
                            shutil.copy2(src_file, dest_file)

                            logger.info(f"复制缺少 PLY 文件的图片: {tiff_file} 到 {group_output_folder}")
                else:
                    logger.warning(f"TIFF 文件夹不存在: {tiff_folder_path}")

        logger.info("所有缺少 PLY 文件的图片组已输出完毕")

    def get_missing_ply_groups(self):
        # 从代理中获取过曝组名称
        if self.delegate:
            missing_ply_groups = self.delegate.missing_ply_group_names
        else:
            missing_ply_groups = set()
        # 打印调试信息
        logger.info(f"过曝组: {missing_ply_groups}")
        return missing_ply_groups

    def get_overexposed_groups(self):
        # 从代理中获取过曝组名称
        if self.delegate:
            overexposed_groups = self.delegate.overexposed_group_names
        else:
            overexposed_groups = set()
        # 打印调试信息
        logger.info(f"过曝组: {overexposed_groups}")
        return overexposed_groups

if __name__ == "__main__":
    # 设置 QApplication 以启动 GUI 应用
    app = QtWidgets.QApplication(sys.argv)

    # 设置 debug_folder\data_combitation 文件夹的路径
    root_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_folder', 'data_combitation')

    # 创建并显示主窗口
    main_window = MainWindow(root_folder, 'C:\\Users\\alienware\\Desktop\\公司实习\\ptcloud_mesh_class\\data-combitation', 'D:\\debug_ptcloud')
    main_window.show()

    # 进入事件循环
    sys.exit(app.exec_())