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
warnings.filterwarnings("ignore", category=DeprecationWarning)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['WANDB_NOTEBOOK_NAME'] = 'dqn.py'

plt.rcParams['figure.dpi'] = 100
device = torch.device( "cpu")


class dqn():
    def __init__(self,exp =edict(),hypp=edict()):

        if exp.set_random_seed:
            random.seed(exp.seed)
            np.random.seed(exp.seed)
            torch.manual_seed(exp.seed)
            torch.backends.cudnn.deterministic = exp.set_random_seed

        self.env = gym.vector.SyncVectorEnv([hf.make_env(exp.env_id, exp.seed + i) for i in range(1)])

        self.rb = ReplayBuffer(
            hypp.buffer_size,
            self.env.single_observation_space,
            self.env.single_action_space,
            device,
        )

        self.env.close()
        self.run_name = f"{exp.env_id}__{exp.exp_name}__{exp.seed}__{datetime.now().strftime('%y%m%d_%H%M%S')}"
        if exp is not None:
            self.exp = exp
        if hypp is not None:
            self.hypp = hypp
        # Init tensorboard logging and wandb logging
        self.writer = hf.setup_logging(f"{exp.env_id}", exp, hypp)


    def train(self):
        # create two vectorized envs: one to fill the rollout buffer with trajectories and
        # another one to evaluate the agent performance at different stages of training
        # Note: vectorized environments reset automatically once the episode is finished
        env = gym.vector.SyncVectorEnv([hf.make_env(self.exp.env_id, self.exp.seed)])
        env_eval = gym.vector.SyncVectorEnv([hf.make_env(self.exp.env_id, self.exp.seed + i) for i in range(1)])

        # init list to track agent's performance throughout training
        tracked_returns_over_training = []
        tracked_episode_len_over_training = []
        tracked_episode_count = []
        last_evaluated_episode = None  # stores the episode_step of when the agent's performance was last evaluated
        eval_max_return = -float('inf')

        # Init observation to start learning
        start_time = time.time()
        obs = env.reset()


        # Create Agent class Instance and network optimizer
        agent = Agent.Agent(env).to(device)
        optimizer = optim.Adam(agent.q_network.parameters(), lr=self.hypp.learning_rate)

        global_step = 0
        episode_step = 0
        gradient_step = 0
        steps = tqdm(range(1, self.hypp.total_timesteps + 1))
        # training loop
        for update in steps:

            epsilon = linear_schedule(self.hypp.start_e, self.hypp.end_e, self.hypp.exploration_fraction * self.hypp.total_timesteps, global_step)
            action = e_greedy_policy(agent, obs, epsilon, env)
            # apply action to environment
            next_obs, reward, done, infos = env.step(action)
            global_step += 1

            # log episode return and length to tensorboard as well as current epsilon
            for info in infos:
                if "episode" in info.keys():
                    print("global step: ", global_step)
                    episode_step += 1
                    steps.set_description(f"global_step: {global_step}, episodic_return={info['episode']['r']}")
                    self.writer.add_scalar("rollout/episodic_return", info["episode"]["r"], global_step)
                    self.writer.add_scalar("rollout/episodic_length", info["episode"]["l"], global_step)
                    self.writer.add_scalar("hyperparameters/epsilon", epsilon, global_step)
                    self.writer.add_scalar("Charts/episode_step", episode_step, global_step)
                    self.writer.add_scalar("Charts/gradient_step", gradient_step, global_step)
                    break

            # ------------------ EVALUATION: DO NOT EDIT ---------------------- #

            # evaluation of the agent
            if self.exp.eval_agent and (episode_step % self.exp.eval_frequency == 0) and last_evaluated_episode != episode_step:
                last_evaluated_episode = episode_step
                tracked_return, tracked_episode_len = hf.evaluate_agent(env_eval, agent, self.exp.eval_count,
                                                                        self.exp.seed, greedy_actor=True)
                tracked_returns_over_training.append(tracked_return)
                tracked_episode_len_over_training.append(tracked_episode_len)
                tracked_episode_count.append([episode_step, global_step])

                # if there has been improvement of the model - save model, create video, log video to wandb
                if np.mean(tracked_return) > eval_max_return:
                    eval_max_return = np.mean(tracked_return)
                    # call helper function save_and_log_agent to save model, create video, log video to wandb
                    hf.save_and_log_agent(self.exp, agent, episode_step,
                                        greedy=True, print_path=False)

            # ----------------------- END EVALUATION ------------------------- #

            # handling the terminal observation (vectorized env would skip terminal state)
            real_next_obs = next_obs.copy()
            for idx, d in enumerate(done):
                if d:
                    real_next_obs[idx] = infos[idx]["terminal_observation"]
            #print(obs)
            # add data to replay buffer
            self.rb.add(obs, real_next_obs, action, reward, done, infos)

            # update obs
            obs = next_obs

            # training of the agent
            if global_step >self.hypp.start_learning:
                if global_step % self.hypp.train_frequency == 0:
                    data = self.rb.sample(self.hypp.batch_size)
                    #print("data: ", data)
                    # Part b)
                    #td_target = compute_TD_target_DDQN(data, agent,hypp.gamma)
                    td_target = compute_TD_target(data, agent,self.hypp.gamma)

                    # calculate loss between target and value
                    old_val = agent.get_q_values(data.observations).gather(1, data.actions).squeeze()
                    loss = ((td_target - old_val)**2).mean()

                    # log td_loss and q_values to tensorboard
                    if global_step % 100 == 0:
                        self.writer.add_scalar("train/td_loss", loss, global_step)
                        self.writer.add_scalar("train/q_values", old_val.mean().item(), global_step)
                        self.writer.add_scalar("others/SPS", int(global_step / (time.time() - start_time)), global_step)
                        self.writer.add_scalar("Charts/episode_step", episode_step, global_step)
                        self.writer.add_scalar("Charts/gradient_step", gradient_step, global_step)

                    # optimize the model
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()
                    gradient_step += 1

                # update the target network
                if global_step % self.hypp.target_network_frequency == 0:
                    agent.synchronize_networks()

        # one last evaluation stage
        if self.exp.eval_agent:
            tracked_return, tracked_episode_len = hf.evaluate_agent(env_eval, agent, self.exp.eval_count, self.exp.seed, greedy_actor = True)
            tracked_returns_over_training.append(tracked_return)
            tracked_episode_len_over_training.append(tracked_episode_len)
            tracked_episode_count.append([episode_step, global_step])

            # if there has been improvement of the model - save model, create video, log video to wandb
            if np.mean(tracked_return) > eval_max_return:
                eval_max_return = np.mean(tracked_return)
                # call helper function save_and_log_agent to save model, create video, log video to wandb
                hf.save_and_log_agent(self.exp, agent, episode_step,
                                    greedy=True, print_path=False)

            hf.save_tracked_values(tracked_returns_over_training, tracked_episode_len_over_training, tracked_episode_count, self.exp.eval_count, self.exp.run_name)


        env.close()
        self.writer.close()
        steps.close()
        if wandb.run is not None:
            wandb.finish(quiet=True)
            wandb.init(mode= 'disabled')

        hf.save_train_config_to_yaml(self.exp, self.hypp)

        if self.hypp.plot_training:
            eval_params = edict()  # eval_params - evaluation settings for trained agent

            eval_params.run_name00 = self.exp.run_name
            eval_params.exp_type00 = self.exp.exp_type

            # eval_params.run_name01 = "CartPole-v1__PPO__1__230302_224624"
            # eval_params.exp_type01 = None

            # eval_params.run_name02 = "CartPole-v1__PPO__1__230302_221245"
            # eval_params.exp_type02 = None

            agent_labels = []

            episode_axis_limit = None

            hf.plotter_agents_training_stats(eval_params, agent_labels, episode_axis_limit, plot_returns=True, plot_episode_len=True)
        if self.hypp.display_evaluation:
            print("Agent")
            agent_name =self. exp.run_name
            agent_exp_type = self.exp.exp_type  # both are needed to identify the agent location
            

            exp_folder = "" if agent_exp_type is None else agent_exp_type
            filepath, _ = hf.create_folder_relative(f"{exp_folder}/{agent_name}/videos")

            hf.record_video(self.exp.env_id, agent_name, f"{filepath}/best.mp4", exp_type=agent_exp_type, greedy=True)

            while True:
                #This is to check whether to break the first loop
                isclosed=0
                cap = cv2.VideoCapture(f"{filepath}/best.mp4")
                while (True):

                    ret, frame = cap.read()
                    # It should only show the frame when the ret is true
                    if ret == True:

                        cv2.imshow('frame',frame)
                        if cv2.waitKey(1) == 27:
                            # When esc is pressed isclosed is 1
                            isclosed=1
                            break
                    else:
                        break
                time.sleep(3)
                # To break the loop if it is closed manually
                if isclosed:
                    break



                cap.release()
                cv2.destroyAllWindows()
            
