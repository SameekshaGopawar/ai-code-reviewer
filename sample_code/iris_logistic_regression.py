# Step 1: Import libraries
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score

# Step 2: Load dataset
data = load_iris()
X = data.data
y = data.target

# Step 3: Split dataset
X_train, y_train, X_test, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Step 4: Create model
model = LogisticRegression(max_iter=200)

# Step 5: Train model
model.fit(X_train, y_train)

# Step 6: Predict
y_pred = model.predict(X_test)

# Step 7: Accuracy
accuracy = accuracy_score(y_test, y_pred)
print("Accuracy:", accuracy)
