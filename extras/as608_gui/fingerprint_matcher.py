from typing import Optional

import numpy as np
import cv2
from cv2.typing import MatLike
from numpy.typing import NDArray

from fingerprint_feature_extractor import extract_minutiae_features
from fingerprint_enhancer import enhance_Fingerprint


class Fingerprint:
    def __init__(self, img: MatLike):
        self.img = img
        self.enhanced_img = enhance_Fingerprint(img)
        self.terminations, self.bifurcations = extract_minutiae_features(img)


def main():
    img1 = cv2.imread("fingerprint1.bmp", cv2.IMREAD_GRAYSCALE)
    # img2 = cv2.imread("fingerprint2.bmp", cv2.IMREAD_GRAYSCALE)
    # img3 = cv2.imread("fingerprint3.bmp", cv2.IMREAD_GRAYSCALE)

    print(img1.shape)

    fp1 = Fingerprint(img1)
    print(fp1.terminations[0])

    cv2.imshow("img1", img1)
    cv2.imshow("img1 ridge segment", fp1.enhanced_img)

    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
