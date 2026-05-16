import numpy as np
import pandas as pd
import pickle
from tensorflow import keras
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, Flatten, Dense
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Load data
data = pd.read_csv("dataset/train.txt", sep=";")
data.columns = ["Text", "Emotion"]

texts = data["Text"].tolist()
labels = data["Emotion"].tolist()

# Tokenization
tokenizer = Tokenizer()
tokenizer.fit_on_texts(texts)

sequences = tokenizer.texts_to_sequences(texts)
max_length = max(len(seq) for seq in sequences)
padded_sequences = pad_sequences(sequences, maxlen=max_length)

# Label encoding
label_encoder = LabelEncoder()
labels_encoded = label_encoder.fit_transform(labels)
one_hot_labels = keras.utils.to_categorical(labels_encoded)

# Train-test split
xtrain, xtest, ytrain, ytest = train_test_split(
    padded_sequences, one_hot_labels, test_size=0.2, random_state=42
)

# Model
model = Sequential([
    Embedding(len(tokenizer.word_index) + 1, 128, input_length=max_length),
    Flatten(),
    Dense(128, activation="relu"),
    Dense(one_hot_labels.shape[1], activation="softmax")
])

model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

model.fit(xtrain, ytrain, epochs=10, batch_size=32, validation_data=(xtest, ytest))

# ✅ SAVE EVERYTHING
model.save("emotion_model.h5")

with open("tokenizer.pkl", "wb") as f:
    pickle.dump(tokenizer, f)

with open("label_encoder.pkl", "wb") as f:
    pickle.dump(label_encoder, f)

with open("max_length.pkl", "wb") as f:
    pickle.dump(max_length, f)
