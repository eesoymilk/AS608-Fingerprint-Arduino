import cv2
import fingerprint_enhancer
import fingerprint_feature_extractor


def main():
    img = cv2.imread("fingerprint.bmp", cv2.IMREAD_GRAYSCALE)

    # enhance the image
    out = fingerprint_enhancer.enhance_Fingerprint(img)

    # extract the minutiae features
    (
        FeaturesTerminations,
        FeaturesBifurcations,
    ) = fingerprint_feature_extractor.extract_minutiae_features(
        out,
        spuriousMinutiaeThresh=10,
        invertImage=False,
        showResult=True,
        saveResult=True,
    )

    # show the image
    # cv2.imshow("image", out)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
