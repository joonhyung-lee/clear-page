"""Stage-specific overview copy, aligned with the supplied manuscript."""
PANELS = {
'grounding': r'''
<p>Affordance-Guided Encoding builds a planning context <span data-tex="\mathbf H"></span> that reflects <mark>the robot’s interaction capabilities and object reachability</mark>. Shared feature encoding and average pooling turn the link, joint, and actuator properties of embodiment <span data-tex="B"></span> into an embedding <span data-tex="\mathbf z_B"></span>.</p>
<p>Conditioned on this embedding and local scene observations, the network predicts an affordance probability <span data-tex="\hat p^{\mathrm{aff}}"></span> for each candidate object interaction or terrain transition. The binary label <span data-tex="b"></span> indicates interaction availability or transition feasibility.</p>
<div class="equation" data-tex="\mathcal L_{\mathrm{aff}}=\operatorname{BCE}(\hat p^{\mathrm{aff}},b)"></div>
<p>When terrain limits movement, path search uses predicted transition probabilities to evaluate scene connectivity and determine which objects are reachable. Object features augmented with these interaction probabilities and reachability information are combined with <span data-tex="\mathbf z_B"></span> and scene observations to form <span data-tex="\mathbf H"></span>, the shared input to OrderNet and CausalFlowNet.</p>
''',
'ordering': r'''
<p>From <span data-tex="\mathbf H"></span>, OrderNet predicts a selection probability <span data-tex="q_i"></span> and Gaussian score parameters <span data-tex="\mu_i,\sigma_i"></span> for each object. Bernoulli sampling selects the object set <span data-tex="\mathcal I"></span>; Gaussian sampling produces latent scores <span data-tex="u_i"></span>. <mark>Sorting selected scores from lowest to highest determines the interaction order.</mark></p>
<div class="equation" data-tex="u_i\sim\mathcal N(\mu_i,\sigma_i^2),\qquad \boldsymbol\rho=\operatorname{argsort}_{i\in\mathcal I}u_i"></div>
<p>Sampling produces alternative object sets and sequences for the same scene and embodiment. Selection considers the complete sequence, including objects that become reachable after earlier interactions. Each candidate uses an object at most once; replanning may select that object again.</p>
<div class="equation" data-tex="\mathcal L_{\mathrm{order}}=\mathcal L_{\mathrm{sel}}+\mathcal L_{\mathrm{rank}}+\lambda_{\mathrm{KL}}\mathcal L_{\mathrm{KL}}"></div>
<p>Binary cross-entropy trains selection. A weighted Bradley–Terry loss encourages lower scores for preceding objects, with more weight on nearby pairs in the training order. Gaussian reparameterization supports gradient-based score learning, and KL regularization keeps the score distributions close to a standard normal distribution.</p>
''',
'generation': r'''
<p>CausalFlowNet generates continuous object parameters with <mark>the selected set, interaction order, and planning context held fixed</mark>. Rank is an object’s position in <span data-tex="\boldsymbol\rho"></span>. The matrix <span data-tex="\mathbf Y_t\in\mathbb R^{N\times D}"></span> stores <span data-tex="D"></span> coordinates per object; <span data-tex="t\in[0,1]"></span> is generation time, not execution time.</p>
<div class="equation" data-tex="\frac{d\mathbf Y_t}{dt}=v_\theta(\mathbf Y_t,t\mid\mathbf H,\boldsymbol\rho)"></div>
<p>Rank-causal attention gives each selected object access to its own token, preceding ranks, and <span data-tex="\mathbf H"></span>. <mark>Generated information cannot enter context tokens</mark>, so later predictions cannot influence earlier ones indirectly through the shared context.</p>
<p>During training, active coordinates of selected objects exclude padding and fixed coordinates. Independent Gaussian noise initializes these coordinates in <span data-tex="\mathbf Y_0"></span>, and <span data-tex="t\sim\mathcal U[0,1]"></span> is sampled for conditional flow matching:</p>
<div class="equation" data-tex="\mathbf Y_t=(1-t)\mathbf Y_0+t\mathbf Y_{\mathrm{target}}"></div>
<div class="equation" data-tex="\mathcal L_{\mathrm{flow}}=\mathbb E\!\left[\left\|\mathbf v_t-(\mathbf Y_{\mathrm{target}}-\mathbf Y_0)\right\|_{\mathrm{act}}^2\right]"></div>
<p>The loss is mean squared error over active coordinates, averaged over training examples, noise, and flow time; it is zero when no active coordinates exist. The combined objective adds ordering, flow, affordance, and optional availability losses:</p>
<div class="equation" data-tex="\begin{aligned}\mathcal L(\theta)={}&\mathcal L_{\mathrm{order}}+\lambda_{\mathrm{flow}}\mathcal L_{\mathrm{flow}}\\&+\lambda_{\mathrm{aff}}\mathcal L_{\mathrm{aff}}+\lambda_{\mathrm{avail}}\mathcal L_{\mathrm{avail}}.\end{aligned}"></div>
<p>The availability term uses training labels to penalize unavailable objects, with normalized first-interaction weights proportional to <span data-tex="q_i\exp(-\mu_i)"></span>; <span data-tex="\lambda_{\mathrm{avail}}=0"></span> when unused.</p>
<p>At inference, integrating from Gaussian noise at <span data-tex="t=0"></span> to <span data-tex="t=1"></span> produces <span data-tex="\mathbf Y_1"></span>. Selected rows are decoded in <span data-tex="\boldsymbol\rho"></span> order into object targets or trajectories <span data-tex="(\xi_1,\ldots,\xi_K)"></span>. Different noise samples yield alternative motions under the same selection and order; the resulting candidates proceed to feasibility checking.</p>
''',
'execution': r'''
<p>Candidate validation checks <mark>robot reachability, collision avoidance, and interaction constraints</mark> in interaction order <span data-tex="\boldsymbol\rho"></span>. Each check uses the scene resulting from preceding object motions. This validation step is omitted in the Grid and Ordered Manipulation evaluations.</p>
<p>Among feasible candidates that satisfy the navigation or arrangement goal <span data-tex="G"></span>, the planner selects the one with <mark>the fewest object interactions</mark>. A valid candidate requiring no interaction has <span data-tex="K=0"></span> and bypasses continuous generation.</p>
<p>For legged robots, an MPC-based controller evaluates candidate command sequences through rollouts of a learned locomotion policy. Quality-diversity optimization retains high-performing and behaviorally diverse sequences, combined with Cartesian tracking and joint-command smoothing.</p>
<p>The controller executes an initial segment of the best evaluated command sequence and updates its optimization using new state estimates. <mark>After each object interaction, updated scene observations guide replanning</mark> of the remaining interactions.</p>
''',
'input-0': r'''
<p>Robot embodiment <span data-tex="B"></span> is described by link, joint, and actuator properties. Shared feature encoding and average pooling construct the embedding <span data-tex="\mathbf z_B"></span>, which conditions predictions of interaction availability and terrain-transition feasibility.</p>
''',
'input-1': r'''
<p>Each movable object <span data-tex="o_i=(x_i,a_i)"></span> has a current configuration <span data-tex="x_i"></span> and physical attributes <span data-tex="a_i"></span>, including geometry and mass. Object motions change the scene and can make subsequent interactions reachable.</p>
''',
'input-2': r'''
<p>The scene <span data-tex="S"></span> contains observed environment geometry, the current robot state, <span data-tex="N"></span> movable objects, and task goal <span data-tex="G"></span>. The goal specifies a navigation destination or desired object arrangement. Terrain connectivity determines which objects the robot can reach.</p>
''',
}


def markup():
    return '<div class="overview-notation">' + ''.join(
        f'<div data-overview-detail="{key}"' + ('' if key == 'grounding' else ' hidden') + '>' + html + '</div>'
        for key, html in PANELS.items()) + '</div>'
