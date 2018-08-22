#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Wed May  9 00:13:25 2018

@author: nimishawalgaonkar
Visual Preference Elicitation
1D and 2D feature defining a state - validated
"""

import numpy as np
import scipy.stats
import sys
sys.path.append('../')
from GPPref import train, predict
from SynOccupant import datagen
from Misc import visualize



class Aquisition(object):
    def __init__(self, X, Y, config_file, model_num,
                 reachable = False):
         """
         Different preference elicitation related aquisition functions
         """
         V = datagen.ThermalPrefDataGen(config_file)
         self.X = X
         self.num_feat = X.shape[1]/2
         self.Y = Y
         self.config_file = config_file
         self.model_num = model_num
         if self.num_feat == 1:
             self.Xtrainnorm = V.normalize1Dpairwise(X)
         elif self.num_feat == 2:
            self.Xtrainnorm = V.normalize2Dpairwise(X)
             
         # Train the model based on training pairwise comparisons
         self.m, self.samples = train.train(self.Xtrainnorm, Y,
                                            config_file, self.model_num)
         
         # Last state (shared state)
         self.Xlaststate = X[-1, self.num_feat:]
         
         # Define reachable states
         RS = datagen.ReachableStates(self.Xlaststate)
         if self.num_feat == 1:
             if reachable:
                 self.Xreachable, self.Xreachablenorm = RS.reachable(config_file)
             else:
                 self.Xreachable, self.Xreachablenorm = RS.rs1D(config_file) # reachable function <---- edit this if you want
         elif self.num_feat == 2:
            sys.exit('Stop!! Currently, this framework only supports 1D features')
            self.Xreachable, self.Xreachablenorm = RS.rs2D(config_file) # reachable function <---- edit this if you want
            
         # Predict GP mean and variance for posterior hyperparameter samples
         Pred = predict.Predict(self.m, self.samples)
         (self.mtrainmat, self.vartrainmat,
          self.mreachablemat, self.varreachablemat) = Pred.u_test_train(self.Xtrainnorm,
                                                             self.Xreachablenorm)
    def sanity_checks(self, iter_num, trial_num, mean_EUI, savefig):
        """
        1. Plotting expected improvement over current state utility
        2. Plotting some utility function samples
        """
         
        visualize.visualize_one_hyper_utility_samples(iter_num, trial_num,
                              self.m, self.samples,
                              self.Xreachablenorm,self.Xreachable,
                              savefig, num_utility = 100)
        visualize.diff_ut(iter_num, trial_num,
                          self.m, self.samples,
                          self.Xreachablenorm, self.Xreachable,
                          savefig, num_gps = 5)
        visualize.visualize_latent_v(self.samples,iter_num, trial_num, savefig)
        visualize.autocorr(self.samples,iter_num, trial_num, savefig)
        visualize.hmc_chains(self.samples,iter_num, trial_num, savefig)
    
        visualize.visualize_EUI(self.Xreachable, mean_EUI,
                                iter_num, trial_num, savefig)
        
    def EUI(self, iter_num, trial_num, savefig = True):
        """
        Selection of next duel based on EUI aquisition function
        (see Herrick conference paper for more details)
        """
        exp_utility_max = np.max(self.mtrainmat, axis = 1)
        mdiff = self.mreachablemat - exp_utility_max[:,None]
        sigreachablemat = np.sqrt(self.varreachablemat)
        Z = mdiff/sigreachablemat
        pdf = scipy.stats.norm.pdf(Z)
        cdf = scipy.stats.norm.cdf(Z)
        exp_imp = mdiff*cdf + sigreachablemat*pdf
        mean_exp_imp = np.mean(exp_imp, axis = 0)
        np.savez(('../data/results/T' + str(trial_num) +
                  '/exp_imp_saves/' + str(iter_num) + '.npz'),
                 mean_exp_imp = mean_exp_imp, iter_num = iter_num,
                 samples = self.samples, X = self.X, Y = self.Y,
                 Xnorm = self.Xtrainnorm, mtrainmat = self.mtrainmat,
                 vartrainmat = self.varreachablemat, mreachmat = self.mreachablemat,
                 varreachmat = self.varreachablemat)
        mean_max_ind = mean_exp_imp.argmax()
        max_exp_imp = mean_exp_imp[mean_max_ind]
        next_state = self.Xreachable[mean_max_ind.astype(int)]
        next_duel = np.hstack([self.Xlaststate, next_state])
        self.sanity_checks(iter_num, trial_num,
                           mean_exp_imp, savefig)
        return (next_state, next_duel, mean_exp_imp, max_exp_imp)
    
    def PE(self, iter_num, trial_num, savefig = True):
        """
        Pure exploration based aquisition function
        """
        
        next_state = self.Xreachable
        return

def seq_learning(X, Y, budget,
                 config_file, trial_num, model_num, reachable,
                 savefig = False):
    """
    Sequential learning framework
    """
    num_feat = X.shape[1]/2
    V = datagen.ThermalPrefDataGen(config_file)
    for i in xrange(budget):
        Aq = Aquisition(X, Y, config_file, model_num, reachable)
        (next_state, next_duel,
         mean_exp_imp, max_exp_imp) = Aq.EUI(i, trial_num, savefig)
        if num_feat == 1:
            Ynew = V.response_gen1D(next_duel[:,None].T)
        if num_feat == 2:
            sys.exit('Framework only supports 1D features')
            utility2D_file = '../data/2Dplotdata/2D.npz'
            Ynew = V.response_gen2D(next_duel[:,None].T) 
            visualize.nxt_point_select2D(next_state, i,
                                         trial_num, utility2D_file, savefig)
        
        X = np.vstack([X, next_duel])
        Y = np.vstack([Y, Ynew])
    return Aq, X, Y
        
if __name__ == '__main__':
    import pandas as pd
    
    config_file = '../config_files/thermal_config.json'
    
    # Load the duels file
    data_file = '../data/duels/duels1.csv' 
    data = pd.read_csv(data_file)
    
    Tprev = np.array(data.Tprev) # previous state (operating temp.)
    Tcurrent = np.array(data.Tcurrent) # current state <---- elicitation framework will give you this values
    X1 = np.vstack([[Tprev, Tcurrent]]).T
    X1 = X1.astype(float) # features need to be float
    Y1 = np.array(data.y)[:,None] # response of the occupant <---- you need to ask occupant about this
    

    budget = 3
    trial_num = 6
    model_num = 2
    savefig = True
    
    S1 = seq_learning(X1, Y1, budget, config_file, trial_num,
                      model_num, savefig)
    