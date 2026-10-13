"""Concise definitions of the joint objective and its component losses."""
ROLES = r'''
<section class="loss-role-guide" aria-label="Component objective definitions">
<div class="loss-role-header">
<h4>Component objectives</h4>
<div class="loss-role-tabs" role="group" aria-label="Inspect an objective term">
<button type="button" data-objective-role="order" aria-pressed="false">Selection / rank</button>
<button type="button" data-objective-role="flow" aria-pressed="false">Generation</button>
<button type="button" data-objective-role="affordance" aria-pressed="false">Feasibility</button>
<button type="button" data-objective-role="availability" aria-pressed="false">Availability</button>
</div>
</div>
<div class="loss-role-panel" data-role-panel="order">
<h5>Object selection and relative order</h5>
<div class="equation" data-tex="\mathcal L_{\mathrm{order}}=\mathcal L_{\mathrm{sel}}+\mathcal L_{\mathrm{rank}}+\lambda_{\mathrm{KL}}\mathcal L_{\mathrm{KL}}"></div>
<p><strong>Binary cross-entropy</strong> supervises object selection; <strong>pairwise ranking</strong> supervises interaction order. <strong>Gaussian KL regularization</strong> constrains the latent score distributions.</p>
<a href="#ordering-samples">Reference plans →</a>
</div>
<div class="loss-role-panel" data-role-panel="flow" hidden>
<h5>Conditional motion generation</h5>
<p><strong>Flow matching</strong> learns a velocity field from Gaussian noise to object configurations or trajectories. Selection and order remain fixed, while rank-causal attention conditions each object on preceding interactions.</p>
<a href="#method-flow">Object reference generation →</a>
</div>
<div class="loss-role-panel" data-role-panel="affordance" hidden>
<h5>Embodiment-conditioned feasibility</h5>
<p><strong>Affordance BCE</strong> supervises interaction availability and terrain-transition feasibility. These predictions augment the planning context shared by OrderNet and CausalFlowNet.</p>
<a href="#grounding-samples">Feasibility samples →</a>
</div>
<div class="loss-role-panel" data-role-panel="availability" hidden>
<h5>First-interaction availability</h5>
<p>The auxiliary loss penalizes unavailable first interactions using normalized weights proportional to <span data-tex="q_i\exp(-\mu_i)"></span>.</p>
<p class="availability-state"><span data-tex="\lambda_{\mathrm{avail}}=0"></span> for the displayed objective.</p>
</div>
</section>
'''

CAPTIONS = {
    'selection': 'Object participation.',
    'order': 'Relative interaction order.',
    'kl': 'Latent score regularization.',
    'flow': 'Continuous object references.',
    'affordance': 'Interaction and terrain feasibility.',
}
