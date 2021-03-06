import os
import argparse
import tensorflow as tf

# The original freeze_graph function
# from tensorflow.python.tools.freeze_graph import freeze_graph 

dir = os.path.dirname(os.path.realpath(__file__))

# Adapter from: https://blog.metaflow.fr/tensorflow-how-to-freeze-a-model-and-serve-it-with-a-python-api-d4f3596b3adc


def freeze_graph(model_dir, output_node_names):
    """Extract the sub graph defined by the output nodes and convert 
    all its variables into constant 

    Args:
        model_dir: the root folder containing the checkpoint state file
        output_node_names: a string, containing all the output node's names, 
                            comma separated
    """
    if not tf.gfile.Exists(model_dir):
        raise AssertionError(
            "Export directory doesn't exists. Please specify an export "
            "directory: %s" % model_dir)

    if not output_node_names:
        print("You need to supply the name of a node to --output_node_names.")
        return -1

    # We retrieve our checkpoint fullpath
    checkpoint = tf.train.get_checkpoint_state(model_dir)
    input_checkpoint = checkpoint.model_checkpoint_path

    # Hack to make this work on our local machines
    # The path given by model_checkpoint_path points to an HDFS address within Hops
    model_checkpoint_path_split = input_checkpoint.split('/')
    model_files_path_with_prefix = \
        model_dir + "/" + model_checkpoint_path_split[len(model_checkpoint_path_split)-1]   # This is of the form 'trained_model/model.ckpt-10001'

    # We precise the file fullname of our freezed graph
    # absolute_model_dir = "/".join(input_checkpoint.split('/')[:-1])
    # Don't want to point to an HDFS address within Hops, but the folder on our local machine instead
    absolute_model_dir = model_dir
    output_graph = absolute_model_dir + "/frozen_model.pb"

    # We clear devices to allow TensorFlow to control on which device it will load operations
    clear_devices = True

    # We start a session using a temporary fresh Graph
    with tf.Session(graph=tf.Graph()) as sess:
        # We import the meta graph in the current default Graph
        saver = tf.train.import_meta_graph(model_files_path_with_prefix + '.meta', clear_devices=clear_devices)

        # We restore the weights
        # saver.restore(sess, input_checkpoint)
        saver.restore(sess, model_files_path_with_prefix)

        # We use a built-in TF helper to export variables to constants
        output_graph_def = tf.graph_util.convert_variables_to_constants(
            sess,   # The session is used to retrieve the weights
            tf.get_default_graph().as_graph_def(),  # The graph_def is used to retrieve the nodes
            output_node_names.split(","),   # The output node names are used to select the usefull nodes
            # Only for estimator API graph
            # Have to black list the global step and global step variable initialization check,
            # otherwise the inferencer doesn't work
            variable_names_blacklist='IsVariableInitialized,global_step'
        ) 

        # Finally we serialize and dump the output graph to the filesystem
        with tf.gfile.GFile(output_graph, "wb") as f:
            f.write(output_graph_def.SerializeToString())
        print("%d ops in the final graph." % len(output_graph_def.node))

    return output_graph_def


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # "tm_11000_learning_rate=0.0001.dropout=0.5"
    # "tm_11000_learning_rate=0.0005.dropout=0.25"
    parser.add_argument("--model_dir", type=str, default="tm_11000_learning_rate=0.0005.dropout=0.25", help="Model folder to export")

    # TFOS model
    # parser.add_argument("--output_node_names", type=str, default="prediction", help="The name of the output nodes, comma separated.")
    # Estimator model
    parser.add_argument("--output_node_names", type=str, default="ArgMax", help="The name of the output nodes, comma separated.")

    args = parser.parse_args()

    freeze_graph(args.model_dir, args.output_node_names)