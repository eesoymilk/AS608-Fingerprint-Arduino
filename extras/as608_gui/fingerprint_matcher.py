from typing import Sequence

import numpy as np
import cv2
import skimage
from skimage.morphology import skeletonize

from cv2.typing import MatLike
from numpy.typing import NDArray

from fingerprint_enhancer import enhance_Fingerprint
from fingerprint_feature_extractor import extract_minutiae_features


class Fingerprint:
    def __init__(self, img: MatLike):
        self.img = img
        self.enhanced_img = enhance_Fingerprint(img)
        self.skeleton_img = np.uint8(skeletonize(self.enhanced_img)) * 255
        self.terminations, self.bifurcations = extract_minutiae_features(
            self.enhanced_img
        )

        self.result_img = cv2.cvtColor(self.skeleton_img, cv2.COLOR_GRAY2BGR)
        for t in self.terminations:
            (rr, cc) = skimage.draw.circle_perimeter(t.locX, t.locY, 3)
            skimage.draw.set_color(self.result_img, (rr, cc), (0, 0, 255))
        for b in self.bifurcations:
            (rr, cc) = skimage.draw.circle_perimeter(b.locX, b.locY, 3)
            skimage.draw.set_color(self.result_img, (rr, cc), (255, 0, 0))


def main():
    img1 = cv2.imread("fingerprint1.bmp", cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread("fingerprint2.bmp", cv2.IMREAD_GRAYSCALE)
    # img3 = cv2.imread("fingerprint3.bmp", cv2.IMREAD_GRAYSCALE)

    fp1 = Fingerprint(img1)
    fp2 = Fingerprint(img2)

    cv2.imshow("img1 result", fp1.result_img)
    cv2.imshow("img2 result", fp2.result_img)

    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
