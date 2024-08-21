import subprocess
import logging
from pyntcloud import PyntCloud
from scipy.spatial import KDTree
from concurrent.futures import as_completed, ProcessPoolExecutor
import os
import numpy as np
import open3d as o3d

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("process.log"),
    logging.StreamHandler()
])
logger = logging.getLogger()

class PLYProcessor:
    def __init__(self, roi_radius, threshold, erosion_ratio, density_threshold):
        self.roi_radius = roi_radius
        self.threshold = threshold
        self.erosion_ratio = erosion_ratio
        self.density_threshold = density_threshold

    def generate_ply(self, data_folder_path, output_folder_path):
        """运行 TestRangeImage.exe 来生成 PLY 文件"""
        test_range_image_exe_path = "C:\\Users\\alienware\\Desktop\\TestRangeImage\\TestRangeImage.exe"  # 修改为实际路径
        command = f'"{test_range_image_exe_path}" "{data_folder_path}" "{output_folder_path}"'
        try:
            logger.info(f"运行命令: {command}")
            result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("TestRangeImage.exe 输出:\n%s", result.stdout.decode())
            if result.stderr:
                logger.error("TestRangeImage.exe 错误:\n%s", result.stderr.decode())
        except subprocess.CalledProcessError as e:
            logger.error("运行 TestRangeImage.exe 时出错:\n返回码: %d\n输出: %s\n错误信息: %s", e.returncode,
                         e.output.decode(), e.stderr.decode())
            raise

    def calculate_curvatures(self, points, tree):
        """计算点云的曲率"""
        curvatures = []
        for point in points[['x', 'y', 'z']].values:
            idx = tree.query_ball_point(point, self.roi_radius)
            if len(idx) < 3:
                curvatures.append(0)
                continue
            neighborhood = points.iloc[idx][['x', 'y', 'z']].values
            distances = np.linalg.norm(neighborhood - point, axis=1)
            valid_idx = distances <= (1 - self.erosion_ratio) * self.roi_radius
            neighborhood = neighborhood[valid_idx]
            if len(neighborhood) < 3:
                curvatures.append(0)
                continue
            covariance = np.cov(neighborhood.T)
            eigvals = np.linalg.eigvalsh(covariance)
            curvature = eigvals[0] / np.sum(eigvals)
            curvatures.append(curvature)
        return curvatures

    def process_ply_file(self, ply_path, output_folder_path):
        """处理 PLY 文件，包括着色和生成网格"""
        logger.info(f"处理 PLY 文件: {ply_path}")
        point_cloud = PyntCloud.from_file(ply_path)
        points = point_cloud.points

        logger.info(f"点云数据加载完成，共 {len(points)} 个点")

        tree = KDTree(points[['x', 'y', 'z']].values)

        if self.roi_radius < 0:
            logger.warning("ROI 半径为负数，使用绝对值进行计算")
            self.roi_radius = abs(self.roi_radius)

        curvatures = self.calculate_curvatures(points, tree)

        points['curvature'] = curvatures
        points['red'] = 0
        points['green'] = 0
        points['blue'] = 0

        if self.roi_radius == 0:
            points.loc[points['curvature'] > self.threshold, ['red', 'green', 'blue']] = [255, 0, 0]
        else:
            var_threshold = float(self.threshold)
            for i, point in points[['x', 'y', 'z']].iterrows():
                idx = tree.query_ball_point(point.values, self.roi_radius)
                neighborhood_curvatures = points.iloc[idx]['curvature'].values
                if len(neighborhood_curvatures) < 2:
                    continue
                curvature_variance = np.var(neighborhood_curvatures)
                if curvature_variance > var_threshold:
                    points.loc[idx, ['red', 'green', 'blue']] = [255, 0, 0]

        points['red'] = np.clip(points['red'], 0, 255)
        points['green'] = np.clip(points['green'], 0, 255)
        points['blue'] = np.clip(points['blue'], 0, 255)

        black_points_count = len(points[(points['red'] == 0) & (points['green'] == 0) & (points['blue'] == 0)])
        red_points_count = len(points[(points['red'] == 255) & (points['green'] == 0) & (points['blue'] == 0)])
        logger.info(f"未超过曲率阈值点的个数: {black_points_count}")
        logger.info(f"超过曲率阈值点的个数: {red_points_count}")

        output_ply_path = os.path.join(output_folder_path, os.path.basename(ply_path).replace('.ply', '_colored.ply'))
        logger.info(f"输出文件: {output_ply_path}")
        with open(output_ply_path, 'w') as f:
            f.write(f"ply\n")
            f.write(f"format ascii 1.0\n")
            f.write(f"element vertex {len(points)}\n")
            f.write(f"property float x\n")
            f.write(f"property float y\n")
            f.write(f"property float z\n")
            f.write(f"property uchar red\n")
            f.write(f"property uchar green\n")
            f.write(f"property uchar blue\n")
            f.write(f"end_header\n")
            for i, row in points.iterrows():
                line = f"{row['x']} {row['y']} {row['z']} {int(row['red'])} {int(row['green'])} {int(row['blue'])}\n"
                f.write(line)

        self.generate_mesh(ply_path, output_folder_path)
        self.generate_mesh(output_ply_path, output_folder_path, colored=True)

    def generate_mesh(self, ply_path, output_folder_path, colored=False):
        """生成网格并应用密度过滤"""
        pcd = o3d.io.read_point_cloud(ply_path)
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)

        densities = np.asarray(densities)
        densities = densities / densities.max() if densities.max() > 0 else densities

        mesh_vertices = np.asarray(mesh.vertices)
        vertex_density = np.zeros(len(mesh_vertices))

        for i, vertex in enumerate(mesh_vertices):
            distances = np.linalg.norm(pcd.points - vertex, axis=1)
            idx_within_radius = distances <= self.roi_radius
            if np.sum(idx_within_radius) > 0:
                vertex_density[i] = np.mean(densities)

        valid_vertices = vertex_density >= self.density_threshold
        mesh = mesh.select_by_index(np.where(valid_vertices)[0])

        suffix = '_colored_filtered_mesh.ply' if colored else '_original_filtered_mesh.ply'
        output_mesh_path = os.path.join(output_folder_path, os.path.basename(ply_path).replace('.ply', suffix))
        o3d.io.write_triangle_mesh(output_mesh_path, mesh)
        logger.info(f"保存网格文件: {output_mesh_path}")

    def process_ply_file_wrapper(self, ply_path, output_folder_path):
        """封装 process_ply_file 以便在多线程中使用"""
        try:
            self.process_ply_file(ply_path, output_folder_path)
        except Exception as e:
            logger.error(f"处理文件 {ply_path} 时出错: {e}")

    def process_all_subfolders(self, root_folder_path, output_folder_path):
        """处理根文件夹下的所有子文件夹"""
        max_workers = min(os.cpu_count() - 4, 100)  # 动态设置线程数
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            for subdir in os.listdir(root_folder_path):
                subdir_path = os.path.join(root_folder_path, subdir)
                if os.path.isdir(subdir_path):
                    output_subfolder = os.path.join(output_folder_path, subdir)
                    os.makedirs(output_subfolder, exist_ok=True)

                    logger.info(f"处理子文件夹: {subdir_path}")
                    self.generate_ply(subdir_path, output_subfolder)

                    for filename in os.listdir(output_subfolder):
                        if filename.endswith('.ply'):
                            ply_path = os.path.join(output_subfolder, filename)
                            futures.append(executor.submit(self.process_ply_file_wrapper, ply_path, output_subfolder))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"处理过程中发生了异常: {e}")

# 示例使用
if __name__ == "__main__":
    processor = PLYProcessor(roi_radius=0.5, threshold=0.0003, erosion_ratio=0.01, density_threshold=0.1)
    processor.process_all_subfolders("C:\\Users\\alienware\\Desktop\\公司实习\\ptcloud_mesh_class\\data-combitation", "D:\\debug_ptcloud")
