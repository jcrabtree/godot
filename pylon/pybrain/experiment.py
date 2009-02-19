#------------------------------------------------------------------------------
# Copyright (C) 2009 Richard W. Lincoln
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 dated June, 1991.
#
# This software is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANDABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#------------------------------------------------------------------------------

""" Defines an experiment that matches up agents with tasks and handles their
    interaction.
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

from pybrain.rl.experiments import Experiment, EpisodicExperiment

from pylon.routine.api import DCOPFRoutine

#------------------------------------------------------------------------------
#  "MarketExperiment" class:
#------------------------------------------------------------------------------

class MarketExperiment(Experiment):
    """ Defines an experiment that matches up agents with tasks and handles
        their interaction.
    """

    stepid = 0

    tasks = list

    agents = list

    # The power system model containing the agent's assets.
    power_sys = None

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self, tasks, agents, power_sys):
        """ Initialises the market experiment.
        """
        super(MarketExperiment, self).__init__(task=None, agent=None)
        assert len(tasks) == len(agents)

        self.tasks = tasks
        self.agents = agents
        self.stepid = 0

        self.power_sys = power_sys

    #--------------------------------------------------------------------------
    #  "Experiment" interface:
    #--------------------------------------------------------------------------

    def doInteractions(self, number=1):
        """ Directly maps the agents and the tasks.
        """
        all_rewards = []
        for interaction in range(number):
            # Perform action for each agent.
            for i, agent in enumerate(self.agents):
                task = self.tasks[i]

                self.stepid += 1
                agent.integrateObservation( task.getObservation() )
                task.performAction( agent.getAction() )

            # Optimise the power system model.
            routine = DCOPFRoutine(self.power_sys, show_progress=False)
            solution = routine.solve()
            if solution["status"] != "optimal":
                print "NO OPTIMAL SOLUTION FOR INTERACTION %d." % interaction
                break

            # Reward each agent appropriately.
            rewards = []
            for i, agent in enumerate(self.agents):
                task = self.tasks[i]

                reward = task.getReward()
                agent.giveReward(reward)

                rewards.append(reward)

            all_rewards.append(rewards)

        return all_rewards

# EOF -------------------------------------------------------------------------
