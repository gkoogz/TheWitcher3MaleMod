"""Exercise the fitted stock skin palette with observed native movement frames.

Read a REDkit dump of man_geralt_movement.w2anims. Support only its observed
normal clips, float-bit compression and XYZSignedWInLastBit orientation format.
For partially streamed clips, sample the inline core and the native constant
fallback for the streamed tail; do not invent or decode absent deferred data.
This checks animation/mesh compatibility offline; it does not run the game.
"""
import argparse
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from mod import ROOT, digest, write_json
from prepare_motion import rig_world
from verify_attachment import skin_weights
from wcc_fbx import Document

CLIPS = ('locomotion_idle', 'walk', 'locomotion_run_cycle_fast_forward')
METHOD = 'ABOCM_AsFloat_XYZSignedWInLastBit'


def prop(obj, name):
    result = obj.find('./properties/prop[@name="' + name + '"]')
    if result is None:
        raise ValueError('Missing native property ' + name)
    return result


def read_clips(path, wanted=CLIPS):
    # Native dumps serialize each resource object on separate lines. Retain
    # only the selected buffers rather than building the entire 200 MB tree.
    header = re.compile(r'^<object class="([^"]+)" id="([0-9]+)"')
    requested, result = {}, {}
    current, lines = None, []

    def consume():
        if not lines:
            return
        obj = ET.fromstring(''.join(lines))
        if current[0] == 'CSkeletalAnimation':
            name = prop(obj, 'name').text
            if name in wanted:
                if prop(obj, 'Animation type for reimport').text != 'SAT_Normal':
                    raise ValueError('Selected clip is additive: ' + name)
                ref = prop(obj, 'animBuffer').find('reference')
                requested[ref.get('id')] = name
        else:
            name = requested[current[1]]
            if prop(obj, 'orientationCompressionMethod').text != METHOD:
                raise ValueError('Uncalibrated native orientation encoding')
            bones = prop(obj, 'bones').find('array')
            if int(bones.get('count')) != 94 or len(bones) != 94:
                raise ValueError('Selected clip does not use the observed 94-joint palette')
            data = bytes(int(e.text) & 255 for e in prop(obj, 'data').findall('./array/element'))
            if not data:
                raise ValueError('Selected clip requires uncalibrated deferred data')
            result[name] = (obj, data)

    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            match = header.match(line)
            if match:
                consume()
                if len(result) == len(wanted):
                    break
                current = match.groups()
                lines = []
            if current and (current[0] == 'CSkeletalAnimation' or
                            current[0] == 'CAnimationBufferBitwiseCompressed' and current[1] in requested):
                lines.append(line)
    if set(result) != set(wanted):
        raise ValueError('Missing selected native clips: ' + repr(set(wanted) - set(result)))
    return result


def track_frame(track, data, frame, frame_count, quaternion=False, fallback=None):
    values = {p.get('name'): p.text for p in track.find('properties')}
    compression = int(values['compression'])
    if compression not in (0, 1, 2):
        raise ValueError('Uncalibrated float-bit compression')
    count = int(values['numFrames'])
    if count not in (1, frame_count):
        raise ValueError('Uncalibrated frame skipping/interpolation')
    width = 4 - compression
    address = int(values['dataAddr']) + (0 if count == 1 else frame) * 3 * width
    if fallback is not None:
        address = int(values['dataAddrFallback'])
        if address >= len(data):
            address -= len(data)
            data = fallback
    if address < 0 or address + 3 * width > len(data):
        raise ValueError('Native track points outside inline data')
    # Native UncompressSingleDataStream masks 32/24/16 bits then shifts by
    # 0/8/16 bits. These are truncated float bits, not normalized integers.
    bits = [int.from_bytes(data[address+i*width:address+(i+1)*width], 'little')
            << (compression * 8) for i in range(3)]
    xyz = np.array([struct.unpack('<f', struct.pack('<I', x))[0] for x in bits])
    if not np.isfinite(xyz).all():
        raise ValueError('Non-finite native frame')
    if not quaternion:
        return xyz
    # The native method takes W's sign from bit zero of Z's first stored
    # byte, keeps XYZ's decoded bits, and clamps squared XYZ length to one.
    w = np.sqrt(max(0., 1. - min(float(xyz @ xyz), 1.)))
    if data[address+2*width] & 1:
        w = -w
    return np.r_[xyz, w]


def model_frames(buffer, data, parents):
    count = int(prop(buffer, 'numFrames').text)
    bones = prop(buffer, 'bones').findall('./array/element/object')
    nonstreamable = int(prop(buffer, 'nonStreamableBones').text)
    fallback = bytes(int(e.text) & 255 for e in prop(buffer, 'fallbackData').findall('./array/element'))
    frames = []
    for frame in range(count):
        worlds = []
        for i, bone in enumerate(bones):
            tail = fallback if i >= nonstreamable else None
            local = np.eye(4)
            local[:3, :3] = Rotation.from_quat(track_frame(
                prop(bone, 'orientation').find('object'), data, frame, count, True, tail)).as_matrix()
            local[:3, :3] *= track_frame(prop(bone, 'scale').find('object'), data, frame, count, fallback=tail)
            local[:3, 3] = track_frame(prop(bone, 'position').find('object'), data, frame, count, fallback=tail) * 100.
            # Reset the rig root like an attached pose. The clip may still
            # contain extracted trajectory in other tracks; do not interpret
            # centroid travel as actor-relative gait amplitude.
            if i == 0:
                local = np.eye(4)
            worlds.append(worlds[parents[i]] @ local if parents[i] >= 0 else local)
        frames.append(worlds)
    return frames


def skin(points, weights, matrices):
    homogeneous = np.c_[points, np.ones(len(points))]
    return np.einsum('nb,bij,nj->ni', weights, np.asarray(matrices)[:, :3], homogeneous)


def audit(dump, rig_recipe, output):
    dump, rig_recipe = Path(dump), Path(rig_recipe)
    rig = json.loads(rig_recipe.read_text())['_chunks']['CSkeleton #0']['_vars']
    names, parents, _ = rig_world(rig)
    if names[9] != 'pelvis' or len(names) not in (94, 104):
        raise ValueError('Observed stock rig changed')
    attachment = json.loads((ROOT/'generated/attachment.json').read_text())
    fit_path = ROOT/attachment['fitReport']
    fit = json.loads(fit_path.read_text())
    source = fit_path.with_name(fit_path.name.replace('.fit.json', '.fbx'))
    if digest(source) != fit['outputSHA256']:
        raise ValueError('Fitted source changed')
    document = Document(source)
    clips = read_clips(dump)
    reports = []
    for lod, mesh in enumerate(document.meshes):
        palette = [n for n, _ in document.skin(mesh)]
        if any(n not in names[:94] for n in palette):
            raise ValueError('Mesh depends on a non-stock animation bone')
        weights = skin_weights(document, mesh, palette)
        inverse_binds = [c.array('Transform').reshape(4,4).T for _, c in document.skin(mesh)]
        points = mesh.array('Vertices').reshape(-1,3)
        binding = np.load(source.with_name(fit['lods'][lod]['bindings']))
        body_count = len(binding['body_lineage_indptr']) - 1
        rigid = np.flatnonzero((np.arange(len(points)) >= body_count) &
                              (weights[:, palette.index('pelvis')] > 1.-1e-10))
        if not len(rigid):
            raise ValueError('No distal pelvis-bound control vertices')
        for name, (buffer, data) in clips.items():
            frames = model_frames(buffer, data, parents[:94])
            seam_error, follow_error = 0., 0.
            first_local, first_tip, tip_travel = None, None, 0.
            for worlds in frames:
                matrices = [worlds[names.index(n)] @ bind for n, bind in zip(palette, inverse_binds)]
                posed = skin(points, weights, matrices)
                seam_error = max(seam_error, float(np.linalg.norm(
                    posed[binding['body_seam']] - posed[binding['module_seam']], axis=1).max()))
                local = np.c_[posed[rigid], np.ones(len(rigid))] @ np.linalg.inv(worlds[9]).T
                tip = posed[rigid].mean(0)
                if first_local is None:
                    first_local, first_tip = local, tip
                follow_error = max(follow_error, float(np.linalg.norm(local-first_local, axis=1).max()))
                tip_travel = max(tip_travel, float(np.linalg.norm(tip-first_tip)))
            if seam_error > 1e-8 or follow_error > 1e-8 or name != 'locomotion_idle' and tip_travel < .01:
                raise ValueError('Native clip did not preserve animated collar/pelvis following')
            reports.append(dict(lod=lod, clip=name, frames=len(frames), stockTracks=94,
                inlineAnimatedBones=int(prop(buffer,'nonStreamableBones').text),
                streamedTail='native constant fallback; deferred frames not sampled',
                seamError=seam_error, pelvisLocalFollowError=follow_error,
                distalCentroidTravelFBXUnits=tip_travel, pelvisBoundControlVertices=len(rigid)))
    result = dict(schemaVersion=1, verification='decoded observed REDkit normal clips; offline skinning',
        observedGameplay=False, nativeDumpSHA256=digest(dump), rigRecipeSHA256=digest(rig_recipe),
        fitReport=attachment['fitReport'], fitReportSHA256=digest(fit_path),
        stockPaletteOnly=True, missingPaletteNames=[], rootBoneReset=True,
        extractedMotionSubtracted=False,
        positionUnits='raw native-export FBX units; not a physical unit claim', results=reports)
    write_json(output, result)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path)
    parser.add_argument('rig_recipe', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    audit(args.dump, args.rig_recipe, args.output)
