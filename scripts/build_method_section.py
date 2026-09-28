"""Build manuscript-aligned method explanations without copying private sources."""
from pathlib import Path
from html import escape
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
def math(tex):return '<div class="equation" data-tex="'+escape(tex,quote=True)+'"></div>'
def code(text):return '<pre class="method-code"><code>'+escape(text.strip())+'</code></pre>'
parts=['<nav class="method-nav" aria-label="Method components"><a href="#method-grounding">(a) Grounding</a><a href="#method-order">(b) Ordering</a><a href="#method-flow">(c) Generation</a><a href="#method-execution">(d) Execution</a></nav>']
parts.append('''<article class="method-part" id="method-grounding"><h3>(a) Embodiment aware scene grounding</h3>
<p class="method-lead">The same geometry can imply different interactions for different bodies.</p>
<p>Shared feature encoders map robot structure, object observations, and scene geometry into a common token space. A masked average summarizes the structural rows. Predicted interaction affordances and navigation information augment the object tokens before attention forms the planning context.</p>
<div class="feature-columns"><div><h4>Morphology</h4><p>Maze embodiments use 20 values per link. These include mass, inertia, geometry scale, tree depth, joint type and axis, joint range, actuator strength, damping, link offset, and reference height. Grid and fixed manipulator tasks use their task specific structural descriptors.</p></div><div><h4>Object</h4><p>Maze object rows contain normalized position, sine and cosine of yaw, size, mass, and friction. Learned affordance and reachability features describe potential interactions. Current inaccessibility does not exclude an object that may become reachable later.</p></div><div><h4>Scene</h4><p>Maze primitives encode location, extent, endpoint heights, slope axis, friction, and semantic flags. The grid adapter uses a spatial scene encoder. Padding masks prevent absent objects or geometry from entering attention.</p></div></div>''')
parts.append(math(r'\begin{aligned}\mathbf z_B&=\frac{\sum_{\ell=1}^{L}m_\ell\,\phi_B(\mathbf b_\ell)}{\max(1,\sum_{\ell=1}^{L}m_\ell)},\\ \hat p_i^{\mathrm{aff}}&=\operatorname{sigmoid}\!\left(f_{\mathrm{aff}}(\mathbf z_B,\mathbf a_i)\right),\\\mathbf h_i^0&=\phi_O(\mathbf o_i)+\phi_N(\mathbf n_i),\\\mathbf H&=\operatorname{Transformer}\!\left([\mathbf z_B,\mathbf h_1^0,\ldots,\mathbf h_N^0,\phi_S(S)]\right).\end{aligned}'))
parts.append(r'''<p>Here, <span class="inline-math" data-tex="\mathbf a_i"></span> is an observed interaction query and <span class="inline-math" data-tex="\mathbf n_i"></span> is the affordance and navigation context. Affordance labels supervise a binary classifier. Ordering and generation losses also backpropagate through the shared encoder.</p>''')
parts.append(math(r'\mathcal L_{\mathrm{aff}}=-\frac{1}{|\mathcal Q|}\sum_{i\in\mathcal Q}\left[b_i\log\hat p_i^{\mathrm{aff}}+(1-b_i)\log(1-\hat p_i^{\mathrm{aff}})\right].'))
parts.append('''<div class="method-interactive" id="context-demo"><div class="control-row"><label>Context token <input id="context-token" type="range" min="0" max="260" value="1"></label><output id="context-label"></output></div><canvas id="context-canvas" width="960" height="300" role="img" aria-label="Actual 128 dimensional context activation vector for the selected token"></canvas><p id="context-readout" class="viewer-note" aria-live="polite"></p><p class="figure-caption">Actual activations from a frozen grid checkpoint. This example contains one structural token, four object tokens, and 256 scene tokens. Color represents signed activation, not an affordance score or a physical quantity.</p></div>''')
parts.append(code('''def forward(self, batch):
    z_B = masked_mean(self.body_mlp(batch.structure), batch.link_mask)
    p_aff = self.affordance(z_B, batch.queries).sigmoid()
    navigation = augment_with_reachability(p_aff, batch.geometry)
    objects = self.object_mlp(batch.objects) + self.nav_map(navigation)
    scene = self.scene_encoder(batch.scene)
    H = self.trunk(concat(z_B[:, None], objects, scene),
                   key_padding_mask=batch.padding_mask)
    return H, p_aff'''))
parts.append('<p class="implementation-note">Pseudocode combines the task adapters into one interface. The maze adapter computes connectivity through path search. The grid affordance adapter directly adds predicted per-object probabilities. Both expose observed geometry to all candidate interaction ranks.</p></article>')
parts.append('''<article class="method-part" id="method-order"><h3>(b) Latent interaction ordering</h3><p class="method-lead">Selection determines which objects participate. Sampled priorities determine their order.</p><p>OrderNet reads the encoded object tokens and predicts a selection logit, a Gaussian mean, and a bounded standard deviation for each object. Gaussian reparameterization provides gradients through the sampled priorities used by the ranking loss.</p>''')
parts.append(math(r'\begin{aligned}(a_i,\mu_i,s_i)&=W\mathbf h_i+c,&q_i&=\operatorname{sigmoid}(a_i),\\ \sigma_i&=\sigma_{\min}+(\sigma_{\max}-\sigma_{\min})\operatorname{sigmoid}(s_i),\\ m_i&\sim\operatorname{Bernoulli}(q_i),& u_i&=\mu_i+\sigma_i\epsilon_i,\quad\epsilon_i\sim\mathcal N(0,1),\\\mathcal I&=\{i:m_i=1\},&\boldsymbol\rho&=\operatorname{argsort}_{i\in\mathcal I}u_i.\end{aligned}'))
parts.append('''<div class="method-interactive"><div class="control-row"><button id="order-resample" type="button">Resample selection and priorities</button><output id="order-result" aria-live="polite"></output></div><canvas id="order-canvas" width="960" height="280" role="img" aria-label="Learned selection probabilities and Gaussian priority distributions"></canvas><p class="figure-caption">Samples use the displayed checkpoint probabilities and Gaussian parameters. A sampled order is a proposal, not a feasibility certificate. The flow panel below holds its recorded order fixed.</p></div><h4>Ordering objective</h4><p>Let <span class="inline-math" data-tex="v_i"></span> mark valid object slots and <span class="inline-math" data-tex="y_i"></span> mark selected targets. Ground truth ranks are zero based, with rank <span class="inline-math" data-tex="N"></span> assigned to unselected objects. A pair receives a larger weight when its objects are closer in the reference order.</p>''')
parts.append(math(r'\begin{aligned}\mathcal L_{\mathrm{sel}}&=-\frac{1}{\sum_i v_i}\sum_i v_i\left[y_i\log q_i+(1-y_i)\log(1-q_i)\right],\\ \mathcal P&=\{(i,j):v_i v_j=1,\ r_i<N,\ r_j>r_i\},\quad w_{ij}=\frac{1}{r_j-r_i},\\\mathcal L_{\mathrm{rank}}&=\frac{\sum_{(i,j)\in\mathcal P}w_{ij}\operatorname{softplus}((u_i-u_j)/T)}{\sum_{(i,j)\in\mathcal P}w_{ij}},\\\mathcal L_{\mathrm{KL}}&=\frac{1}{2\sum_i v_i}\sum_i v_i\left[\mu_i^2+\sigma_i^2-1-\log\sigma_i^2\right],\\\mathcal L_{\mathrm{order}}&=\mathcal L_{\mathrm{sel}}+\mathcal L_{\mathrm{rank}}+\lambda_{\mathrm{KL}}\mathcal L_{\mathrm{KL}}.\end{aligned}'))
parts.append('<p class="implementation-note">Sums pool valid entries and pairs across the minibatch. Empty supervision produces a differentiable zero. The grid checkpoint restricts ranking pairs to selected objects. Other shared adapters also include selected versus unselected pairs. This ordering head uses σ<sub>min</sub> = 0.05, σ<sub>max</sub> = 0.5, and T = 1.</p>')
parts.append(code('''def forward(self, object_tokens):
    selection, mu, raw = self.head(object_tokens).unbind(-1)
    sigma = 0.05 + 0.45 * sigmoid(raw)
    return selection, mu, sigma

def ordering_loss(self, selection, mu, sigma, rank, valid):
    selected = valid & (rank >= 0) & (rank < rank.shape[-1])
    u = mu + sigma * randn_like(mu)
    L_sel = masked_bce_with_logits(selection, selected, valid)
    r = where(selected, rank, rank.shape[-1])
    pairs = valid_pairs(r, valid, selected_only=self.selected_only)
    gap = u[:, None, :] - u[:, :, None]
    w = reciprocal_rank_distance(r, pairs)
    L_rank = weighted_mean(softplus(-gap / temperature), w)
    L_KL = masked_mean(0.5 * (mu**2 + sigma**2 - 1) - log(sigma), valid)
    return L_sel + L_rank + lambda_KL * L_KL'''))
parts.append('</article>')
parts.append(r'''<article class="method-part" id="method-flow"><h3>(c) Rank causal generation</h3><p class="method-lead">The generator predicts how selected objects should move while respecting the proposed order.</p><p>Observed scene and robot information remains available throughout generation. Generated targets from later ranks cannot influence earlier ranks. Context tokens cannot read generated tokens, which also prevents an indirect information path through subsequent attention layers.</p>
<div class="method-interactive"><div class="control-row"><label>Process <select id="flow-mode"><option value="inference">Checkpoint inference</option><option value="training">Training interpolation</option></select></label><label>Noise draw <select id="flow-seed"><option value="0">1</option><option value="1">2</option><option value="2">3</option><option value="3">4</option></select></label><button id="flow-play" type="button">Play</button><label>Flow time <input id="flow-time" type="range" min="0" max="100" value="0"></label><output id="flow-time-value">t = 0.00</output></div><div class="flow-panels"><canvas id="flow-canvas" width="640" height="540" role="img" aria-label="Object targets evolving on the observed grid"></canvas><canvas id="mask-canvas" width="420" height="540" role="img" aria-label="Rank causal attention between observed context and generated object targets"></canvas></div><p id="flow-readout" class="figure-caption" aria-live="polite"></p><p class="implementation-note">Inference displays the network’s actual Euler states for four noise draws. Lines between stored states are display interpolation only. Training mode shows the prescribed straight interpolation to the demonstration target. Neither mode is robot execution.</p></div>
<h4>Flow matching objective</h4><p>The active mask includes selected objects and excludes padding or fixed target coordinates. Training samples one flow time per example. The implemented loss pools active coordinates across the minibatch, denoted by <span class="inline-math" data-tex="\mathcal B"></span>. The velocity target is the displacement from the sampled noise to the demonstrated target.</p>''')
parts.append(math(r'\begin{aligned}A_{id}&=\mathbf1[i\in\mathcal I]\,c_{id},\quad \mathbf E\sim\mathcal N(0,I),\quad t\sim\mathcal U[0,1],\\\mathbf Y_0&=A\odot(\sigma_0\mathbf E),\quad\bar{\mathbf Y}_{\mathrm{target}}=A\odot\mathbf Y_{\mathrm{target}},\\\mathbf Y_t&=(1-t)\mathbf Y_0+t\bar{\mathbf Y}_{\mathrm{target}},\\\mathbf v_t&=v_\theta(\mathbf Y_t,t\mid\mathbf H,\boldsymbol\rho),\\\mathcal L_{\mathrm{flow}}&=\mathbb E_{\mathcal B,\mathbf E,t}\!\left[\frac{\sum_{b\in\mathcal B}\sum_{i,d}A_{bid}\left(v_{t_b,bid}-(\bar Y_{\mathrm{target},bid}-Y_{0,bid})\right)^2}{\max(1,\sum_{b\in\mathcal B}\sum_{i,d}A_{bid})}\right].\end{aligned}'))
parts.append(math(r'M_{ij}=\begin{cases}0&j\text{ is observed context},\\0&i,j\text{ are generated and }r_j\le r_i,\\-\infty&\text{otherwise}.\end{cases}\qquad\mathbf Y_{k+1}=\mathbf Y_k+\Delta t\,A\odot v_\theta(\mathbf Y_k,t_k\mid\mathbf H,\boldsymbol\rho).'))
parts.append('<p class="implementation-note">The attention rule additionally masks absent keys. The manuscript uses σ<sub>0</sub> = 1. The displayed maze trace uses 30 Euler steps, Δt = 1/30, and σ<sub>0</sub> = 0.01. Flow time and controller time are distinct.</p>')
parts.append(code('''def forward(self, H, Y_t, t, rank, selected, valid_keys):
    generated = self.target_embed(H.objects, Y_t, time_embed(t))
    observed = self.target_embed(H.objects, zeros_like(Y_t), time_embed(t))
    tokens = concat(H.body, generated, H.scene, observed)
    blocked = rank_causal_mask(rank, selected) | ~valid_keys[:, None, :]
    return self.velocity_head(self.trunk(tokens, mask=blocked).objects)

def flow_loss(self, H, target, rank, selected, coordinate_mask):
    active = selected[..., None] & coordinate_mask
    Y_0 = where(active, sigma_0 * randn_like(target), 0)
    target = where(active, target, 0)
    t = uniform_per_example(target.shape[0])
    Y_t = (1 - t) * Y_0 + t * target
    velocity = self.forward(H, Y_t, t, rank, selected, H.valid_keys)
    return mean_over_active((velocity - (target - Y_0))**2, active)

def generate(self, H, rank, selected, coordinate_mask, steps=30):
    active = selected[..., None] & coordinate_mask
    Y = where(active, sigma_0 * randn_target(), 0)
    for k in range(steps):
        v = self.forward(H, Y, k / steps, rank, selected, H.valid_keys)
        Y = Y + where(active, v, 0) / steps
    return decode_selected_rows(Y, rank)'''))
parts.append('''<section class="objective"><h4>The full training objective</h4><p>The shared objective combines selection, ranking, Gaussian regularization, continuous generation, and affordance supervision. An availability penalty discourages an unavailable first interaction without prohibiting an object from participating later in the plan.</p>''')
parts.append(math(r'\begin{aligned}\alpha_i&=\frac{q_i e^{-\mu_i}}{\sum_{j\in\mathcal V}q_j e^{-\mu_j}},\\\mathcal L_{\mathrm{avail}}&=\mathbb E_{\mathrm{data}}\!\left[\sum_{i\in\mathcal V}\alpha_i(1-b_i)\right],\\\mathcal L(\theta)&=\mathcal L_{\mathrm{sel}}+\mathcal L_{\mathrm{rank}}+\lambda_{\mathrm{KL}}\mathcal L_{\mathrm{KL}}\\&\quad+\lambda_{\mathrm{flow}}\mathcal L_{\mathrm{flow}}+\lambda_{\mathrm{aff}}\mathcal L_{\mathrm{aff}}+\lambda_{\mathrm{avail}}\mathcal L_{\mathrm{avail}}.\end{aligned}'))
parts.append(math(r'\mathcal L_{\mathrm{card}}=\mathbb E_{\mathrm{data}}\!\left[\left(\sum_i v_i q_i-\sum_i v_i y_i\right)^2\right],\qquad\mathcal L_{\mathrm{grid,impl}}=\mathcal L+0.1\mathcal L_{\mathrm{card}}.'))
parts.append('''<p class="implementation-note">Inspected settings: λ<sub>KL</sub> = 0.001 and λ<sub>flow</sub> = 1. Grid uses λ<sub>aff</sub> = 1 and λ<sub>avail</sub> = 0, with the additional cardinality coefficient 0.1 shown above. The recorded ordered manipulation checkpoint uses λ<sub>aff</sub> = 1 and λ<sub>avail</sub> = 1. The inspected maze training configuration uses λ<sub>aff</sub> = 10 and no availability penalty. These are task specific settings rather than one universal coefficient vector.</p>
<ol class="training-steps"><li><strong>Observe and encode.</strong> Construct masked structural, object, and scene tokens and predict affordances.</li><li><strong>Supervise selection and order.</strong> Use demonstration selections and ranks with reparameterized priority samples.</li><li><strong>Supervise generation.</strong> Sample noise and flow time, interpolate active target coordinates, and regress the conditional velocity.</li><li><strong>Update shared parameters.</strong> Sum the configured losses and backpropagate through the shared encoder and prediction heads. Maze training includes an affordance warmup before joint updates.</li></ol>''')
parts.append(code('''def training_step(batch):
    H, p_aff = encode_and_ground(batch.observations)
    L_sel, L_rank, L_KL = order_losses(H, batch.selected, batch.rank)
    L_flow = flow_loss(H, batch.target, batch.rank, batch.active)
    L_aff = supervised_affordance_loss(p_aff, batch.affordance_labels)
    L_avail = first_interaction_penalty(H.q, H.mu, batch.affordance_labels)
    loss = (L_sel + L_rank + lambda_KL * L_KL + lambda_flow * L_flow
            + lambda_aff * L_aff + lambda_avail * L_avail)
    if grid_cardinality_weight:
        loss += grid_cardinality_weight * cardinality_loss(H.q, batch.selected)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()'''))
parts.append('</section></article>')
parts.append('''<article class="method-part" id="method-execution"><h3>(d) Execution and replanning</h3><p class="method-lead">The planner checks the consequences of each interaction and updates the remaining plan after execution.</p><p>For maze navigation, candidate plans are checked in their proposed order for reachability, collision avoidance, and interaction constraints. A feasible plan with the fewest object interactions is selected. Grid and ordered manipulation evaluations omit this post-generation feasibility filter.</p><p>The legged controller evaluates command sequences through rollouts of a locomotion policy. Quality and behavioral diversity guide candidate retention. Cartesian tracking and joint command smoothing convert the selected sequence into executable motion. Only the initial segment is applied before the controller updates from a new state estimate.</p><p>When high level replanning is enabled, the resulting observation becomes the input to a new plan after an object interaction. The long horizon evaluation tests this update explicitly, while the maze navigation comparison retains its initial high level plan. An object may therefore be selected again in a later planning cycle even though each individual plan contains at most one interaction per object.</p></article>''')

# Insert implementation details inside the final execution article.
parts[-1]=parts[-1].removesuffix('</article>')
parts.append('<label class="scenario-control">MPC view <select id="mpc-view"><option value="robot">Robot and candidates</option><option value="candidates">Candidate detail</option></select></label><div class="experiment-matrix paired-matrix mpc-comparison">')
for key,label in [('mpc-optimized','Optimized MPC (ours)'),('mpc-baseline','Naive MPC')]:
 parts.append(f'<article><h4>{label}</h4><div class="viewer experiment-viewer" data-scene="{key}" data-title="{label}"><img class="preview-image" src="assets/media/{key}.png" alt="Recorded robot mesh and MPC candidate hand trajectories" width="700" height="540" loading="lazy"><button class="launch" type="button">Play in 3D</button></div></article>')
parts.append('</div><p class="figure-caption">Recorded first object interaction from a matched development comparison. Gray curves show candidate palm trajectories, teal identifies retained elites, and orange marks the candidate applied by the controller. Both hands and all 24 candidates are included. Rotate or zoom the scene to inspect their spatial extent. Candidate detail removes the robot shell and centers each population at the current palm midpoint. The grid spacing is 0.1 m.</p><p class="implementation-note">Both runs use the same scene, planning and motor checkpoints, seed, 0.6 s rollout horizon, and 0.1 s executed segment. Naive MPC uses top-k selection without the added temporal cost. Optimized MPC combines LA-QDPP with λ<sub>s</sub> = 0.25 and a contact-phase arm filter coefficient of 0.2, from a shared base coefficient of 0.4. This comparison changes both selection and smoothing, so it does not isolate the effect of LA-QDPP. Each panel follows its own recorded timing. These are development demonstrations, not aggregate benchmark results.</p>')
parts.append('<h4>Candidate selection and temporal regularization</h4><p>MPC samples a population of control knots around the current nominal sequence. Piecewise linear interpolation evaluates each sequence over the rollout horizon. The ordinary CEM baseline retains the highest scoring candidates. LA-QDPP balances rollout quality with novelty among the retained candidates.</p>')
parts.append(math(r'\begin{aligned}\mathbf K^{(n)}&=\operatorname{clip}(\bar{\mathbf K}+\boldsymbol\Sigma\odot\boldsymbol\epsilon^{(n)},-1,1),\\q_n&=\exp\!\left(\frac{R_n-\max_m R_m}{\operatorname{std}(R)+10^{-9}}\right),\\\mathbf z_n&=\operatorname{vec}\!\left(\mathbf K^{(n)}/(\boldsymbol\Sigma+10^{-9})\right),\\S_{nm}&=\exp\!\left(-\frac{\|\mathbf z_n-\mathbf z_m\|^2}{2\ell^2}\right)\mathbf1[\|\mathbf z_n-\mathbf z_m\|\le2\ell],\\n^*&=\operatorname{argmax}_{n\notin\mathcal E}\ q_n^2\left(1-\max_{m\in\mathcal E}S_{nm}^2\right),\\\bar{\mathbf K}&\leftarrow\frac1{|\mathcal E|}\sum_{n\in\mathcal E}\mathbf K^{(n)}.\end{aligned}'))
parts.append('<p class="implementation-note">The nominal sequence is retained as candidate zero. The local selector first keeps at most 4k candidates by quality, where k is the elite count. It initializes the elite set with the highest quality candidate. The bandwidth is half the square root of the median pairwise squared distance. Degenerate distances use a fallback scale. This nearest selected approximation is a diversity heuristic, not exact DPP sampling.</p>')
parts.append('<p>Diversity selection alone does not impose temporal smoothness. The optional contact conditioned rollout cost separately penalizes palm acceleration, changes in applied commands, and drift from the contact anchor. Palm positions are expressed in the predicted object frame so that intended object motion is not treated as contact drift.</p>')
parts.append(math(r'\begin{aligned}C_{\mathrm{smooth},t}=\lambda_s\!\left[2p_t\,\underset{h}{\operatorname{mean}}\left\|\frac{\mathbf a_{t,h}}{a_0}\right\|^2+\frac{p_t}{2}\,\underset{j}{\operatorname{mean}}\left(\frac{u_{t,j}-u_{t-1,j}}{u_0}\right)^2\right.\\\left.\qquad+\frac14\max\!\left(0,\frac{p_t-0.2}{0.8}\right)\underset{h}{\operatorname{mean}}\left\|\frac{\mathbf x_{t,h}-\mathbf x_{\mathrm{anchor},h}}{d_0}\right\|^2\right].\end{aligned}'))
parts.append('<p class="implementation-note">Implementation scales are a<sub>0</sub> = 10 m/s², u<sub>0</sub> = 0.25, and d<sub>0</sub> = 0.05 m. They are development normalization scales, not hardware limits. The phase weight transitions from 0.2 during approach or reacquisition to 1 after recent measured contact. Setting λ<sub>s</sub> = 0 disables this cost. Its use is separate from the choice of elite selector.</p>')
parts.append(code("""def control_step(self, measured_state):
    self.rollout_bank.clone_state(measured_state)
    knots = self.optimizer.sample(guide=self.guide)
    commands = self.optimizer.interpolate(knots)
    trajectories, task_cost = self.rollout_bank.simulate(commands)
    cost = task_cost + temporal_cost(trajectories, commands)
    self.optimizer.update(knots, reward=-cost)
    chosen = argmin(cost)
    self.optimizer.shift(self.executed_time)
    self.execute(commands[chosen, :self.apply_steps])"""))
parts.append('<p class="implementation-note">In the inspected full path controller, the elite mean updates the proposal distribution for future cycles. Execution applies the best evaluated candidate’s initial segment. It does not directly execute an untested average of elite commands.</p>')
parts.append('</article>')
soup=BeautifulSoup((root/'index.html').read_text(),'html.parser');method=soup.find(id='method')
for child in list(method.children):
 if getattr(child,'name',None) and not (child.get('id') == 'clear-overview' or 'section-heading' in child.get('class',[]) or child.name in ['figure','details']):child.decompose()
abstract=method.find('details',class_='abstract');content=BeautifulSoup(''.join(parts),'html.parser')
abstract.insert_before(content)
for tag,attrs in [('link',{'href':'assets/katex/katex.min.css','rel':'stylesheet'}),('script',{'src':'assets/katex/katex.min.js','defer':''}),('script',{'src':'assets/method-trace.js','defer':''}),('script',{'src':'assets/method.js','defer':''})]:
 key='href' if tag=='link' else 'src'
 if not soup.find(tag,attrs={key:attrs[key]}):soup.head.append(soup.new_tag(tag,attrs=attrs))
(root/'index.html').write_text(str(soup).rstrip()+'\n')
print('Built sequential Method sections, full objectives, and implementation pseudocode.')

# Apply the scene-led presentation after rebuilding the detailed source.
import runpy
runpy.run_path(str(root/"scripts/compact_method.py"))
