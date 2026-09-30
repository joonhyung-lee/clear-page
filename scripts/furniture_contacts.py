"""Extend CLEAR's box contact filter to observed furniture surfaces.

The original filter excludes the top ten percent of an object's bounding box.
For a table, that excludes its entire usable rim. This adapter retains the
original cloud gates, learned scores, selection and pair constraints, changing
the upper height bound to a 1 cm margin below the actual object height.
Bilateral contacts must also share a height and front plane, with their midpoint
near the object center, to avoid selecting a seat with one hand and a backrest
with the other.
Object size, geometry and pose are never changed. Contacts remain observed
RGB-D points, with the original explicit fallback when no pair is available.
"""
import numpy as np
from clear.maze.ego_affordance import (
    EgoAffordance, ContactSet, _unit, _support_half, _object_cloud,
    privileged_contact_set, pick_qd,
)


class FurnitureEgoAffordance(EgoAffordance):
    def contact_set(self, frame, oid, obj_xy, obj_yaw, dx_m, dy_m, height_m, target_xy, part, *, support_z=0.0):
        self.last_selection = None
        obj_xy = np.asarray(obj_xy, float)
        d = _unit(np.asarray(target_xy, float) - obj_xy)
        lat = np.array([-d[1], d[0]])
        visibility = dict(first_empty_gate=None, kinematic_reach_tested=False)
        def fb(why):
            result = privileged_contact_set(obj_xy, obj_yaw, dx_m, dy_m, height_m, target_xy, part, why)
            result.points[:, 2] += support_z
            result.visibility = dict(visibility)
            return result
        # (1) behind gate: the camera must look roughly along the push direction
        fwd = -np.asarray(frame.cam_xmat, float)[:, 2]
        if _unit(fwd[:2]) @ d < self.behind_cos_min:
            visibility['first_empty_gate'] = 'camera_heading'
            return fb('not behind')
        # (2) segmented ego cloud
        pts, rgb, pix = _object_cloud(frame, oid)
        visibility['object_points'] = len(pts)
        if len(pts) < 12:
            visibility['first_empty_gate'] = 'object_visibility'
            return fb('object not in view')
        # (3) prefilter on the REAL cloud: height band, back face, lateral extent, reach
        half_along = _support_half(obj_yaw, dx_m, dy_m, d)
        half_lat = _support_half(obj_yaw, dx_m, dy_m, lat)
        z_lo, z_hi = support_z + part.h_min, support_z + min(part.h_max, height_m - 0.01)
        rel = pts[:, :2] - obj_xy
        along, lat_rel = rel @ d, rel @ lat
        visibility['height_band_m'] = [float(z_lo), float(z_hi)]
        visibility['observed_height_range_m'] = [float(pts[:, 2].min()), float(pts[:, 2].max())]
        gates = [('height_band', (pts[:, 2] >= z_lo) & (pts[:, 2] <= z_hi)),
                 ('back_face', along <= -0.35 * half_along),
                 ('lateral_extent', np.abs(lat_rel) <= 1.05 * half_lat)]
        if getattr(part, 'reach_m', 0.0) > 0:
            gates.append(('coarse_camera_reach', np.linalg.norm(
                pts[:, :2] - np.asarray(frame.cam_xpos, float)[:2], axis=1) <= part.reach_m + self.reach_slack_m))
        m = np.ones(len(pts), dtype=bool)
        for name, gate in gates:
            m &= gate
            visibility[name + '_points'] = int(m.sum())
            if not m.any() and visibility['first_empty_gate'] is None:
                visibility['first_empty_gate'] = name
        if not m.any():
            return fb('no candidates')
        cand, cpix, lat_c = pts[m], pix[m], lat_rel[m]
        # (4) score: low and centred wins; contact_net (if loaded) sharpens around its argmax
        z_preferred = z_lo if self.contact_prior_height_m is None else float(np.clip(support_z+self.contact_prior_height_m,z_lo,z_hi))
        q = (np.exp(-(lat_c / (0.5 * half_lat + 1e-6)) ** 2)
             * np.exp(-0.5 * ((cand[:, 2] - z_preferred) / 0.15) ** 2))
        scorer = 'analytic'
        if self.scoring_mode=='uniform':
            # Random candidate ranking with identical cloud, prefilter, output
            # space and pair constraints. This ablates learned/analytic scores.
            q=self.rng.random(len(cand))
            scorer='uniform_candidate_ranking'
        elif self._net is not None:
            try:
                from clear.mj_util.contact_net import sample_contact_learned
                local_pts = pts.copy(); local_pts[:, 2] -= support_z
                learned_height = (0.5 * (z_lo + z_hi) if self.contact_prior_height_m is None else z_preferred) - support_z
                cs = sample_contact_learned(local_pts, rgb, d, push_height_m=learned_height,
                                            net=self._net, device=self.device, mode='argmax', rng=self.rng)
                if cs.ok:
                    world_point = np.asarray(cs.point_world) + np.array([0., 0., support_z])
                    q = q * np.exp(-((cand - world_point) ** 2).sum(1) / 0.05 ** 2)
                    scorer = 'contact_net'
            except Exception:
                pass
        q = q / max(q.max(), 1e-12)
        # (5) la-QDPP pick of k = n_contacts
        k = int(getattr(part, 'n_contacts', 1))
        sep = float(getattr(part, 'pair_separation_m', 0.0))
        ell = 0.5 * sep if k == 2 and sep > 0 else 0.10
        picked = (pick_qd(cand / ell, q, k, local=True) if self.selector == 'laqdpp'
                  else np.argsort(-q, kind='stable')[:k])
        initial_picked = picked.copy()
        used_fallback = False
        reason = 'ok'
        if k == 2:
            def pair_mask(i):
                lateral = np.abs(lat_c-lat_c[i])
                front = (cand[:, :2]-obj_xy) @ d
                return ((lateral >= .8*sep) & (lateral <= 1.2*sep)
                        & (np.abs(cand[:, 2]-cand[i, 2]) < .025)
                        & (np.abs(front-front[i]) < .04)
                        & (np.abs((lat_c+lat_c[i])/2) < .04))
            ok_pair = lambda i, j: bool(pair_mask(i)[j])
            if self.pair_mode=='centered':
                # A learned peak may sit near either edge and create a large
                # yaw moment. Use observed points around the measured box-face
                # centre while retaining the requested contact height.
                center=np.r_[obj_xy-d*half_along,z_preferred]
                offset=np.r_[lat*sep/2,0.]
                symmetric=np.array([np.argmin(np.sum((cand-(center-offset))**2,axis=1)),
                                    np.argmin(np.sum((cand-(center+offset))**2,axis=1))])
                if ok_pair(*symmetric):
                    picked=symmetric
                else:
                    # The independently nearest pixels can miss the separation
                    # bound by one sample. Search only nearby left anchors for
                    # the closest feasible observed pair.
                    right=center+offset
                    for i in np.argsort(np.sum((cand-(center-offset))**2,axis=1))[:64]:
                        feasible = pair_mask(i)
                        if feasible.any():
                            j=int(np.argmin(np.where(feasible,np.sum((cand-right)**2,axis=1),np.inf)))
                            picked=np.array([int(i),j]);break
            if len(picked) < 2 or not ok_pair(*picked):
                used_fallback = True
                # A high-scoring singleton can have no feasible partner. Picking
                # two independent offsets around it can select the same point,
                # falsely declaring a visible, usable hand pair unavailable.
                # Search anchors by score; each partner must satisfy the actual
                # pair constraints. O(N) working memory, deterministic ties.
                picked = None
                for i in np.argsort(-q, kind='stable'):
                    feasible = pair_mask(i)
                    if feasible.any():
                        partner = int(np.argmax(np.where(feasible,q,-np.inf)))
                        picked = np.array([int(i),partner])
                        break
                if picked is None:
                    self.last_selection = dict(selector=self.selector, feasible_fallback=True, available=False)
                    visibility['first_empty_gate'] = 'pair_geometry'
                    return fb('pair infeasible')
        self.last_selection = dict(selector=self.selector, feasible_fallback=used_fallback, available=True,
                                   initial_picked=initial_picked.tolist(), final_picked=picked.tolist())
        return ContactSet(points=cand[picked].astype(float), source='ego', reason=reason,
                          part_name=part.name, push_dir=d, n_candidates=int(len(cand)),
                          candidates=cand, candidate_pix=cpix, scores=q, picked=np.asarray(picked),
                          scorer=scorer, visibility=visibility)
