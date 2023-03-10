#PPO
import gym
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.distributions import Categorical
import time
import numpy as np 

learning_rate = 2.5e-4
gamma 		  = 0.99
lmbda 		  = 0.95
eps_clip 	  = 0.1
K_epoch 	  = 4		#how often to update the network (@train_net)
T_horizon 	  = 128

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class PPO(nn.Module):
    def __init__(self):
        super(PPO, self).__init__()
        self.data = []

        self.fc1 = nn.Linear(8, 256)
        self.fc_pi = nn.Linear(256, 4)
        self.fc_v = nn.Linear(256, 1)
        self.optimizer = optim.Adam(self.parameters(), lr=learning_rate)

    #policy network	
    def pi(self, x, softmax_dim = 0):
        x = F.relu(self.fc1(x))
        x = self.fc_pi(x)
        prob = F.softmax(x, dim=softmax_dim)
        return prob

    #value network
    def v(self, x):
        x = F.relu(self.fc1(x))
        v = self.fc_v(x)
        return x

    def put_data(self, transition):
        self.data.append(transition)

    def make_batch(self):
        s_lst, a_lst, r_lst, s_prime_lst, prob_a_lst, done_lst = [], [], [], [], [], []
        for transition in self.data:
            s, a, r, s_prime, prob_a, done = transition

            s_lst.append(s)
            a_lst.append([a])
            r_lst.append([r])
            s_prime_lst.append(s_prime)
            prob_a_lst.append([prob_a])
            done_mask = 0 if done else 1
            done_lst.append([done_mask])
        s, a, r, s_prime, done_mask, prob_a = torch.tensor(s_lst, dtype=torch.float), torch.tensor(a_lst),\
                                                torch.tensor(r_lst), torch.tensor(s_prime_lst, dtype=torch.float), \
                                                torch.tensor(done_lst, dtype = torch.float), torch.tensor(prob_a_lst)
        self.data = []
        return s, a, r, s_prime, done_mask, prob_a

    #GAE
    def train_net(self):
        s, a, r, s_prime, done_mask, prob_a = self.make_batch()
        print("r: ", r)
        print("s: ", s_prime)
        for i in range(K_epoch):
            td_target = r+gamma*self.v(s_prime)*done_mask # Q_pi
            delta = td_target-self.v(s) # A_pi
            delta=delta.detach().numpy()

            advantage_lst = []
            advantage = 0.0
            for delta_t in delta[::-1]:
                advantage = gamma*lmbda*advantage + delta_t[0]
                advantage_lst.append([advantage])
            advantage_lst.reverse()
            advantage = torch.tensor(advantage_lst, dtype=torch.float)

            pi = self.pi(s, softmax_dim = 1)
            pi_a = pi.gather(1, a)

            ratio = torch.exp(torch.log(pi_a)-torch.log(prob_a))

            surr1 = ratio*advantage
            surr2 = torch.clamp(ratio, 1-eps_clip, 1+eps_clip)*advantage
            loss = -torch.min(surr1, surr2) + F.smooth_l1_loss(td_target.detach(), self.v(s))

            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()

def main():
    env = gym.make('LunarLander-v2')
    model = PPO()

    f = open("./log_ppo.txt", "a")
    f.write(time.strftime('%m-%d %H:%M:%s', time.localtime(time.time())))
    
    score = 0.0
    print_interval = 20

    for n_epi in range(200000):
        s = env.reset()
        done = False

        while not done:
            for t in range(T_horizon):
                prob = model.pi(torch.from_numpy(s).float())
                m = Categorical(prob)
                a = m.sample().item()
                s_prime, r, done, info = env.step(a)
                model.put_data((s, a, r/100.0, s_prime, prob[a].item(), done))
                s = s_prime

                score += r
                if done:
                    break
            model.train_net()
            
        if n_epi%print_interval == 0 and n_epi!=0:
            data ="# of episode: {}, avg score: {:.1f}\n".format(n_epi, score/print_interval) 
            print(data)
            f.write(data)
            score = 0.0

    env.close()
    f.write(time.strftime('%m-%d %H:%M:%s', time.localtime(time.time())))
    f.close()

if __name__ == '__main__':
    main()