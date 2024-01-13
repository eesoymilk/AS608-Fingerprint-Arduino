from typing import Optional

import numpy as np
import cv2
from cv2.typing import MatLike
from numpy.typing import NDArray


def ridge_segment(norm_img: NDArray[np.float32], block_size: int, threshold: float):
    """
    Function identifies ridge regions of a fingerprint image and returns a the
    identifying this region. It also normalises the intesity values of the
    image so that the ridge regions have zero mean, unit standard deviation.

    This function breaks the image up into blocks of size block_size ** 2 and
    evaluates the standard deviation in each region. If the standard deviation
    is above the threshold it is deemed part of the fingerprint. Note that the
    image is normalised to have zero mean, unit standard deviation prior to
    performing this process so that the threshold you specify is relative to a
    unit standard deviation.

    Args:
        norm_img: Fingerprint image to be segmented.
        block_size: Block size over which the the standard deviation is
        threshold: Threshold of standard deviation to decide if a block is a
        ridge region.

    Returns:
        norm_img: Image where the ridge regions are renormalised to have zero
        mean, unit standard deviation.
        mask: Mask indicating ridge-like regions of the image, 0 for non ridge
    """

    rows, cols = norm_img.shape
    new_rows = np.intc(
        block_size * np.ceil((np.float32(rows)) / (np.float32(block_size)))
    )
    new_cols = np.intc(
        block_size * np.ceil((np.float32(cols)) / (np.float32(block_size)))
    )

    padded_img = np.zeros((new_rows, new_cols))
    stddevim = np.zeros((new_rows, new_cols))
    padded_img[0:rows][:, 0:cols] = norm_img
    for i in np.arange(0, new_rows, block_size):
        for j in np.arange(0, new_cols, block_size):
            block = padded_img[i : i + block_size][:, j : j + block_size]
            stddevim[i : i + block_size][:, j : j + block_size] = np.std(
                block
            ) * np.ones(block.shape)

    stddevim = stddevim[0:rows][:, 0:cols]
    mask = stddevim > threshold
    mean_val = np.mean(norm_img[mask])
    std_val = np.std(norm_img[mask])
    norm_img = (norm_img - mean_val) / (std_val)

    return norm_img, mask


class FingerprintMatcher:
    def __init__(self, img: MatLike):
        self.img = img
        self.norm_img: Optional[MatLike] = None
        self._enhanced_img: Optional[MatLike] = None

    def _enhance(self):
        cv2.normalize(self.img, self.norm_img, 0, 1, cv2.NORM_MINMAX)
        self.norm_img, mask = ridge_segment(self.norm_img, 16, 0.1)
        self._enhanced_img = self.norm_img

    def _extract_minutiae(self):
        pass

    @property
    def enhanced_img(self):
        if self._enhanced_img is None:
            self._enhance()
        return self._enhanced_img


def main():
    img1 = cv2.imread("fingerprint1.bmp", cv2.IMREAD_GRAYSCALE)
    # img2 = cv2.imread("fingerprint2.bmp", cv2.IMREAD_GRAYSCALE)
    # img3 = cv2.imread("fingerprint3.bmp", cv2.IMREAD_GRAYSCALE)

    print(img1.shape)

    fp1 = FingerprintMatcher(img1)

    print("hello")

    cv2.imshow("img1", img1)
    cv2.imshow("img1 ridge segment", fp1.enhanced_img)

    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
