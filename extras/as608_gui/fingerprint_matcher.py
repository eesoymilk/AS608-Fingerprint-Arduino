from pathlib import Path
from typing import Sequence

import numpy as np
import cv2
import skimage
from skimage.morphology import skeletonize

from cv2.typing import MatLike
from numpy.typing import NDArray

from fingerprint_enhancer import enhance_Fingerprint
from fingerprint_feature_extractor import extract_minutiae_features


class Minutia:
    def __init__(self, x: int, y: int, angle: float, type: str):
        self.x = x
        self.y = y
        self.angle = angle
        self.type = type

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, Minutia):
            return NotImplemented

        if self.type != __value.type:
            return False

        minutia_type = self.type
        d = distance(self, __value)
        da = angle_difference(self.angle, __value.angle)
        if minutia_type == "termination":
            return d <= 17.5 and da <= 30
        else:
            return d <= 17.5


def distance(m1: Minutia, m2: Minutia) -> float:
    """Calculate the Euclidean distance between two minutiae"""
    dx = float(m1.x - m2.x)
    dy = float(m1.y - m2.y)
    return np.sqrt(dx * dx + dy * dy)


def angle_difference(a1: float, a2: float) -> float:
    """Calculate the difference between two angles, in degrees"""
    return np.abs((a1 - a2 + 180) % 360 - 180)


def match_minutiae(
    minutiae1: Sequence[Minutia], minutiae2: Sequence[Minutia]
) -> int:
    """
    Match two fingerprints based on their minutiae.
    """
    n_matches = 0
    matched_indices = []
    for m1 in minutiae1:
        for i, m2 in enumerate(minutiae2):
            if i not in matched_indices and m1 == m2:
                n_matches += 1
                matched_indices.append(i)
                break
    return n_matches


def align_image(img: MatLike) -> NDArray[np.uint8]:
    """Align the image so that the center of mass is at the center"""
    center_of_mass = np.mean(
        np.column_stack(np.where(img > 0)), axis=0, dtype=int
    )
    rows, cols = img.shape
    center = (cols // 2, rows // 2)
    translation = (
        center[0] - center_of_mass[1],
        center[1] - center_of_mass[0],
    )
    translation_matrix = np.float32(
        [[1, 0, translation[0]], [0, 1, translation[1]]]
    )
    return cv2.warpAffine(img, translation_matrix, (cols, rows))


class Fingerprint:
    def __init__(self, img: MatLike):
        self.img = img
        self.enhanced_img = enhance_Fingerprint(img)
        self.skeleton_img: NDArray[np.int8] = (
            np.uint8(skeletonize(self.enhanced_img)) * 255
        )
        self.aligned_img = align_image(self.skeleton_img)

        terminations, bifurcations = extract_minutiae_features(self.aligned_img)

        self.minutiae = [
            *[
                Minutia(t.locX, t.locY, t.Orientation[0], "termination")
                for t in terminations
            ],
            *[
                Minutia(b.locX, b.locY, b.Orientation[0], "bifurcation")
                for b in bifurcations
            ],
        ]

        self.result_img = cv2.cvtColor(self.aligned_img, cv2.COLOR_GRAY2BGR)
        for t in terminations:
            (rr, cc) = skimage.draw.circle_perimeter(t.locX, t.locY, 3)
            skimage.draw.set_color(self.result_img, (rr, cc), (0, 0, 255))
        for b in bifurcations:
            (rr, cc) = skimage.draw.circle_perimeter(b.locX, b.locY, 3)
            skimage.draw.set_color(self.result_img, (rr, cc), (255, 0, 0))

    def save(self, db_dir: Path, name: str):
        fp_dir = db_dir / name
        fp_dir.mkdir(exist_ok=True)
        cv2.imwrite(str(fp_dir / "original.bmp"), self.img)
        cv2.imwrite(str(fp_dir / "enhanced.bmp"), self.enhanced_img)
        cv2.imwrite(str(fp_dir / "skeleton.bmp"), self.skeleton_img)
        cv2.imwrite(str(fp_dir / "aligned.bmp"), self.aligned_img)
        cv2.imwrite(str(fp_dir / "result.bmp"), self.result_img)


def main():
    db_dir = Path(__file__).parent / "db"
    for fp_path in db_dir.glob("*/original.bmp"):
        name = fp_path.parent.name
        print(f"Processing {name}")


if __name__ == "__main__":
    main()
