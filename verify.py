from deepface import DeepFace
import os

#Absolute paths to images
img1 = r"C:\Users\ASUS\OneDrive\Desktop\Python 2025\Project\testimages\user1_1.jpg"
img2 = r"C:\Users\ASUS\OneDrive\Desktop\Python 2025\Project\testimages\user1_2.jpg"

#Check if images exist
print("Image 1 exists:", os.path.exists(img1))
print("Image 2 exists:", os.path.exists(img2))

#Perform face verification
result = DeepFace.verify(
    img1_path=img1,
    img2_path=img2,
    model_name="VGG-Face",
    enforce_detection=True  #detect a face
)

#Print final result
print("\nVerification Result:")
print("Verified:",result["verified"])
print("Distance:",result["distance"])
