import math
import random


def sigmoid(z):
    return 1 / (1 + math.exp(-z))


class LogisticRegression:
    def __init__(self, n_features, weights=[]):
        self.weights = weights
        self.bias = 0
        self.n_features = n_features

    def predict_proba(self, x):
        z = self.bias
        for i in range(self.n_features):
            z += self.weights[i] * x[i]
        return sigmoid(z)

    def predict(self, x):
        return 1 if self.predict_proba(x) > 0.5 else 0

    def train(self, X, y, learning_rate, epochs):
        self.weights = [0] * self.n_features
        for epoch in range(epochs):
            for x, label in zip(X, y):
                pred = self.predict_proba(x)
                error = pred - label
                for i in range(self.n_features):
                    self.weights[i] -= learning_rate * error * x[i]
                self.bias -= learning_rate * error


def generate_data(n_samples):
    X = []
    y = []
    for _ in range(n_samples):
        x1 = random.uniform(-5, 5)
        x2 = random.uniform(-5, 5)
        label = 1 if x1 + x2 > 0 else 0
        X.append([x1, x2])
        y.append(label)
    return X, y


X, y = generate_data(200)

model = LogisticRegression(n_features=2)
model.train(X, y, learning_rate=0.1, epochs=50)

correct = 0
for x, label in zip(X, y):
    if model.predict(x) == label:
        correct = correct + 1

print("Training accuracy:", correct / len(X))
