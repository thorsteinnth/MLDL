from __future__ import division
import tensorflow as tf
from PIL import Image
import numpy as np
import os
from glob import glob
from collections import defaultdict
from operator import add


# Adapted from: https://blog.metaflow.fr/tensorflow-how-to-freeze-a-model-and-serve-it-with-a-python-api-d4f3596b3adc


def load_graph(frozen_graph_filename):
    # We load the protobuf file from the disk and parse it to retrieve the unserialized graph_def
    with tf.gfile.GFile(frozen_graph_filename, "rb") as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())

    # Then, we import the graph_def into a new Graph and returns it
    with tf.Graph().as_default() as graph:
        # The name var will prefix every op/nodes in your graph
        # Since we load everything in a new graph, this is not needed
        tf.import_graph_def(graph_def, name="prefix")
    return graph


def image_to_array(img_path):
    img_file = Image.open(img_path)
    img_decoded = np.array(img_file)
    return img_decoded.reshape(-1, 128, 128, 1)


def get_image_file_paths(folder_path):
    paths = glob(folder_path + '/*.png')
    return paths


def get_genre_png(file_path):
    file_name = os.path.basename(file_path)
    # png file names are of the form genre_....png
    genre = os.path.splitext(file_name)[0].split("_")[0]
    return genre


# https://stackoverflow.com/a/3787983
def all_same(items):
    return all(x == items[0] for x in items)


def print_dictionary(name, dictionary):
    print(name)
    for key, value in dictionary.items():
        print(str(key) + ": " + str(value))


if __name__ == '__main__':

    frozen_model_path = "tm_11000_learning_rate=0.0001.dropout=0.5/frozen_model.pb"
    # frozen_model_path = "tm_11000_learning_rate=0.0005.dropout=0.25/frozen_model.pb"

    graph = load_graph(frozen_model_path)

    # We can verify that we can access the list of operations in the graph
    for op in graph.get_operations():
        print(op.name)

    # We access the input and output nodes
    # Note: We have two different graphs types, one from the TFOS model and one from the TF Estimator API

    # Input
    # x = graph.get_tensor_by_name('prefix/Reshape:0')    # TFOS model
    x = graph.get_tensor_by_name('prefix/ConvNet_1/Reshape:0')  # Estimator model

    # Output
    # y = graph.get_tensor_by_name('prefix/prediction:0')    # TFOS model
    # pkeep = graph.get_tensor_by_name('prefix/pkeep:0') # TFOS model
    y = graph.get_tensor_by_name('prefix/ArgMax:0') # Estimator model


    # NOTE: Model expects batches of 100. Can't do smaller batches, but can do a single image.
    # Will also return 100 identical prediction values for each image.
    # Just hacking around this by predicting each and every image.

    label_dict = {
        'Classical': 0,
        'Techno': 1,
        'Pop': 2,
        'HipHop': 3,
        'Metal': 4,
        'Rock': 5
    }

    class_folders = [
        "data/testing/Classical",
        "data/testing/Techno",
        "data/testing/Pop",
        "data/testing/HipHop",
        "data/testing/Metal",
        "data/testing/Rock"
    ]

    # We launch a Session
    with tf.Session(graph=graph) as sess:

        total_predictions = 0
        total_correct = 0

        for class_folder in class_folders:

            print("Processing class folder: {}".format(class_folder))

            class_predictions = 0
            class_correct = 0

            image_paths = get_image_file_paths(class_folder)
            predictions = defaultdict(int)

            count = 1
            for image_path in image_paths:

                if count % 100 == 0 or count == 1:
                    print("Processing image {} of {}".format(count, len(image_paths)))

                genre = get_genre_png(image_path)
                label = label_dict.get(genre)

                y_out = sess.run(y, feed_dict={
                    x: image_to_array(image_path),
                    # pkeep: 1   # TFOS model
                })

                # Since the TFOS model expects batches of 100 we get 100 identical values as the prediction (with pkeep=1)
                # (The prediction tensor is of shape 100x6)
                if not all_same(y_out):
                    print("WARNING - not all the predicted values are the same for {}".format(image_path))

                predicted_label = y_out[0]
                match = label == predicted_label
                if match:
                    class_correct = class_correct + 1
                    total_correct = total_correct + 1
                class_predictions = class_predictions + 1
                total_predictions = total_predictions + 1
                # print("{} - {} - Predicted: {} - Match: {}".format(label, genre, predicted_label, match))
                predictions[predicted_label] = add(predictions[predicted_label], 1)
                count = count + 1

            print_dictionary("Predictions - {}".format(class_folder), predictions)
            print("Total: {} - Correct: {} - Accuracy: {}\n"
                  .format(str(class_predictions), str(class_correct), str(class_correct / class_predictions)))

        print("Final result - Total: {} - Correct: {} - Accuracy: {}"
              .format(str(total_predictions), str(total_correct), str(total_correct / total_predictions)))

