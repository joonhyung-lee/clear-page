"""Explain how the objective terms combine and expose recorded generation outputs."""
ROLES = r'''
<section class="loss-role-guide" aria-label="How the objective terms work together">
<h4>Component objectives</h4>
<div class="loss-role-tabs" role="group" aria-label="Inspect an objective term">
<button type="button" data-objective-role="order" aria-pressed="true">Selection / rank</button>
<button type="button" data-objective-role="flow" aria-pressed="false">Generation</button>
<button type="button" data-objective-role="affordance" aria-pressed="false">Feasibility</button>
<button type="button" data-objective-role="availability" aria-pressed="false">Availability · weight 0</button>
</div>
<div class="loss-role-panel" data-role-panel="order">
<h5>Choose the objects, then learn their relative order.</h5>
<div class="equation" data-tex="\mathcal L_{\mathrm{order}}=\mathcal L_{\mathrm{sel}}+\mathcal L_{\mathrm{rank}}+\lambda_{\mathrm{KL}}\mathcal L_{\mathrm{KL}}"></div>
<p><strong>Selection BCE</strong> trains each participation probability <span data-tex="q_i"></span>. <strong>Ranking</strong> trains lower latent scores for objects that should come first. <strong>KL regularization</strong> keeps the score distributions near a standard normal, with weight 0.001 in this run. The selected objects and their sorted scores define the sequence that conditions generation.</p>
<a href="#ordering-samples">Inspect reference plans →</a>
</div>
<div class="loss-role-panel" data-role-panel="flow" hidden>
<h5>Generate the object motion under the chosen order.</h5>
<p><strong>Flow matching</strong> trains a velocity field from Gaussian noise toward reference object configurations or trajectories. Generation keeps the selected set and order fixed; rank-causal attention lets an object use earlier ranks. This loss trains continuous targets, while selection and ranking train the discrete sequence.</p>
<a href="#method-flow">Inspect generated object references →</a>
</div>
<div class="loss-role-panel" data-role-panel="affordance" hidden>
<h5>Ground the plan in what the robot can reach and interact with.</h5>
<p><strong>Affordance BCE</strong> learns binary interaction availability or terrain-transition feasibility from labels. These predictions augment object features and reachability information in the shared planning context used by both OrderNet and CausalFlowNet.</p>
<a href="#grounding-samples">Inspect feasibility samples →</a>
</div>
<div class="loss-role-panel" data-role-panel="availability" hidden>
<h5>Discourage an unavailable first interaction.</h5>
<p>The auxiliary penalty uses availability labels and normalized first-interaction weights proportional to <span data-tex="q_i\exp(-\mu_i)"></span>. It links object selection and priority scores to which interaction can start the plan; an object may still become reachable after an earlier interaction.</p>
<p class="availability-state"><strong>Inactive in this run:</strong> <span data-tex="\lambda_{\mathrm{avail}}=0"></span>. Its contribution to the full objective is zero. No availability-loss curve was logged.</p>
</div>
</section>
'''

CAPTIONS = {
    'selection': 'Participation probabilities: which objects belong in the plan.',
    'order': 'Pairwise supervision: earlier objects receive lower latent scores.',
    'kl': 'Latent score regularization. Shown unweighted; contribution is × 0.001.',
    'flow': 'Velocity-field regression: turn noise into continuous object targets.',
    'affordance': 'Binary supervision: interaction availability and terrain feasibility.',
}
