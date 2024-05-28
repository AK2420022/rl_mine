import os
import copy
import time
import random
import warnings
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
from tqdm import notebook
from easydict import EasyDict as edict
from IPython.display import Video
import Agent as Agent
import utils.helper_fns as hf
from dqn_helpers import linear_schedule,compute_TD_target,e_greedy_policy,compute_TD_target_DDQN
from tqdm import tqdm
import gym
import wandb
import torch
import torch.nn as nn
import torch.optim as optim
from stable_baselines3.common.buffers import ReplayBuffer
from moviepy.editor import *
import cv2
import time
from dqn import dqn
device = torch.device( "cpu")

#initialization of dictionaries
exp = edict()

exp.exp_name = 'DQN' # algorithm name, in this case it should be 'DQN'
exp.env_id = 'CartPole-v1' # name of the gym environment to be used in this experiment. Eg: Acrobot-v1, CartPole-v1, MountainCar-v0
exp.device = device.type # save the device type used to load tensors and perform tensor operations

exp.set_random_seed = True # set random seed for reproducibility of python, numpy and torch
exp.seed = 2

# name of the project in Weights & Biases (wandb) to which logs are patched. (only if wandb logging is enabled)
# if the project does not exist in wandb, it will be created automatically
wandb_prj_name = f"RLLBC_{exp.env_id}"

# name prefix of output files generated by the notebook
exp.run_name = f"{exp.env_id}__{exp.exp_name}__{exp.seed}__{datetime.now().strftime('%y%m%d_%H%M%S')}"

#initialize hyperparameters
hypp = edict()

# flags for logging purposes
exp.enable_wandb_logging = True
exp.capture_video = True

# flags to generate agent's average performance during training
exp.eval_agent = True # disable to speed up training
exp.eval_count = 10
exp.eval_frequency = 1000

# putting the run into the designated log folder for structuring
exp.exp_type = None # directory the run is saved to. Should be None or a string value

# agent training specific parameters and hyperparameters
hypp.total_timesteps = 500000 # the training duration in number of time steps
hypp.learning_rate = 2.5e-4 # the learning rate for the optimizer
hypp.gamma = 0.99 # decay factor of future rewards
hypp.buffer_size = 50000 # the size of the replay memory buffer
hypp.target_network_frequency = 500 # the frequency of synchronization with target network
hypp.batch_size = 128# number of samples taken from the replay buffer for one step
hypp.start_e = 1 # probability of exploration (epsilon) at timestep 0
hypp.end_e = 0.01 # minimal probability of exploration (epsilon)
hypp.exploration_fraction =0.5 # the fraction of total_timesteps it takes to go from start_e to end_e
hypp.start_learning = 10000 # the timestep the learning starts (before that the replay buffer is filled)
hypp.train_frequency = 20 # the frequency of training
hypp.display_evaluation = True #display video evaluation
hypp.plot_training = True # plot training
# Initialization of Replay Buffer - DO NOT EDIT

dqn = dqn(exp,hypp)
dqn.train()