"""Author a separate minimal gameplay world. Never installs or edits saves.

Native acceptance and gameplay must be recorded separately from JSON authoring.
Only owned copies are passed to REDkit. The 159 writer is used for new resources;
no stock 162/163 world is forced through the older parser.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
from mod import ROOT, settings, digest, write_json, run_wcc, build, validate_readonly_depot
from prepare_motion import scalar, array, reference, handle, vector
from iteration_clipmap import read_tiles,inspect_clipmap
from iteration_layer_ownership import inspect_layers

WORLD = 'levels/malemod_iteration/malemod_iteration.w2w'
LAYER = 'levels/malemod_iteration/floor.w2l'
GAME = 'levels/malemod_iteration/malemod_iteration.redgame'
QUEST = 'levels/malemod_iteration/iteration.w2quest'
STOCK_BOOTSTRAP = 'quests/prologue/quest_files/q002_emhyr/q002_fistfight_test_quest.w2quest'
FLOOR = 'levels/malemod_iteration/floor.w2mesh'
ENV = 'levels/malemod_iteration/neutral.env'
TERRAIN_MATERIAL = 'levels/malemod_iteration/terrain_material.w2mg'
TERRAIN_TILE = 'levels/malemod_iteration/terrain_tiles/tile_0_x_0_res1024.w2ter'
TERRAIN_TILE_SOURCE = 'engine/reference_level/world/terrain_tiles/tile_0_x_0_res1024.w2ter'
ENV_SOURCE = 'engine/reference_level/environment/definitions/level_global/env_level_v09_tm.env'
TERRAIN_PHYSICAL_MAP = 'gameplay/globals/terrain_textures_physical_materials.csv'
TERRAIN_CHECKER = 'engine\\reference_level\\world\\engine_checker.xbm'
WORLD_DIMENSIONS = 256


def validate_world_dimensions(value):
    """SDK CWorld::InitializeOcclusionCulling derives 256-unit tile counts.

    TerrainSize and the visible studio floor are separate dimensions. A world
    extent of128 produces zero occlusion tiles and violates the native assertion
    iWorldDimensions % iTileSize == 0 (world.cpp line2755).
    """
    import math
    if not math.isfinite(value) or value < 256 or value != int(value) or int(value) % 256:
        raise ValueError('World dimensions must be a positive multiple of native occlusion tile size256')
    return int(value)//256


def terrain_physical_map(cfg, workspace):
    """Add the SDK donor checker to an owned map; preserve stock rows exactly."""
    source=cfg['redkit']/'r4data'/TERRAIN_PHYSICAL_MAP
    original=source.read_bytes()
    materials=(cfg['redkit']/'r4data/gameplay/globals/physical_materials.csv').read_text()
    if not any(row.startswith('stone_solid;') for row in materials.splitlines()):
        raise ValueError('Measured native physical material stone_solid missing')
    if TERRAIN_CHECKER.lower() in original.decode().lower():
        raise ValueError('SDK checker mapping changed; review instead of duplicate')
    target=workspace/TERRAIN_PHYSICAL_MAP
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(original+(b'' if original.endswith(b'\n') else b'\r\n')+
        (TERRAIN_CHECKER+';stone_solid\r\n').encode())
    if not target.read_bytes().startswith(original):
        raise ValueError('Original terrain mapping rows changed')
    return dict(stockSHA256=digest(source),ownedSHA256=digest(target),
        addedTexture=TERRAIN_CHECKER,physicalMaterial='stone_solid',originalRowsPreserved=True)


def external(kind, path, class_name, is_handle=False):
    fields = {'_depotPath': scalar('string', path.replace('/', '\\')),
              '_className': scalar('string', class_name),
              # CSoft.Write matches import flags as well as class/path. The
              # writer always generates EImportFlags.Soft=4 for soft imports.
              '_flags': scalar('Uint16', 4 if kind.startswith('soft:') else 0)}
    if is_handle:
        fields['_chunkHandle'] = scalar('bool', False)
    return {'_type': kind, '_vars': fields}


def transform(position=(0, 0, 0), scale=None):
    fields = {k: scalar('Float', v) for k, v in zip('XYZ', position)}
    if scale is not None:
        fields.update({k: scalar('Float', v) for k, v in zip(('Scale_x', 'Scale_y', 'Scale_z'), scale)})
    return {'_type': 'EngineTransform', '_vars': fields}


def resource(chunks):
    return {'_type': 'CR2W', '_extension': '', '_imports': [], '_properties': [],
            '_buffers': [], '_embedded': [], '_chunks': {
                key: {'_type': key.split(' #')[0], '_key': key, '_parentKey': parent,
                      '_flags': 0, '_vars': fields} for key, parent, fields in chunks}}


def guid(name):
    return scalar('CGUID', base64.b64encode(uuid.uuid5(uuid.NAMESPACE_URL, 'malemod:iteration:'+name).bytes_le).decode())


def verify_native_links(cfg, workspace, job, label, stock_bootstrap=False, existing_depot=None):
    """Official post-conversion readback; a successful cook alone is insufficient."""
    dumps = {}
    commands = []
    reusable_depot = existing_depot
    for resource_path in [GAME, WORLD, LAYER, QUEST]:
        owned = job/('readback-'+label)/Path(resource_path).name
        owned.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace/resource_path, owned)
        commands.append(run_wcc(cfg,'dumpfile',['-file='+str(owned),'-out=\\\\?\\'],
            workspace, 'iteration-'+label+'-links',existing_depot=reusable_depot))
        if reusable_depot is None:
            args=commands[-1]['args']
            reusable_depot=Path(args[args.index('-uncookDir')+1])
        dumps[resource_path] = ET.parse(str(owned)+'.xml').getroot()
    def props(path, cls, object_id=None):
        objects=dumps[path].find('objects')
        found=[o for o in objects.iter('object') if o.get('class')==cls and o.find('properties') is not None
               and (object_id is None or o.get('id')==object_id)]
        if len(found)!=1: raise ValueError('Native object missing or ambiguous: '+cls)
        return {p.get('name'):p for p in found[0].find('properties')}
    def path_value(node, expected):
        if node is None: raise ValueError('Native reference property missing: '+expected)
        resource=node.find('resource')
        value=(resource.get('path') if resource is not None else node.text or '').strip().replace('\\','/').lower()
        if value != expected.lower(): raise ValueError('Native reference differs: '+repr(value)+' != '+expected)
    game=props(GAME,'CWitcherGameResource')
    path_value(game['worlds'].find('array/element/object/properties/prop[@name="world"]'),WORLD)
    path_value(game['defaultPlayerTemplate'],'gameplay/templates/characters/player/player.w2ent')
    path_value(game['defaultCameraTemplate'],'gameplay/camera/new_camera.w2ent')
    path_value(game['mainQuest'],QUEST)
    path_value(game['huntingClueCategoryResource'],'game/hunting_clues_enums.csv')
    pins=game['mapPinConfig'].find('object/properties/prop[@name="pinTypes"]/array')
    if pins is None or pins.get('count')!='1' or pins.find('element/object/properties/prop[@name="typeName"]').text!='Quest':
        raise ValueError('Native game definition lacks the measured stock Quest map pin type')
    world=props(WORLD,'CGameWorld')
    world_dimensions=float(world['worldDimensions'].text)
    occlusion_tiles=validate_world_dimensions(world_dimensions)
    terrain=world['terrainClipMap'].find('reference')
    if terrain is None or terrain.get('class')!='CClipMap': raise ValueError('Native world clipmap is NULL')
    clip=props(WORLD,'CClipMap',terrain.get('id'))
    for name in ('clipSize','clipmapSize','tileRes','numTilesPerEdge'):
        if int(clip[name].text)<=0: raise ValueError('Native clipmap setting invalid: '+name)
    total=int(clip['clipmapSize'].text);size=int(clip['clipSize'].text)
    if size<256 or size&(size-1) or size>total or not 64<=total<=65536:
        raise ValueError('Native terrain dimensions violate SDK Reinit assertions')
    expected_levels=0;reduced=total
    while reduced>size:
        reduced>>=1;expected_levels+=1
    if int(clip['numClipmapStackLevels'].text)!=expected_levels:
        raise ValueError('Native clipmap stack differs from SDK authoring derivation')
    path_value(clip['material'],TERRAIN_MATERIAL)
    if read_tiles((workspace/WORLD).read_bytes())!=[TERRAIN_TILE]:
        raise ValueError('Native clipmap custom tile topology differs')
    mip_sizes=inspect_clipmap((workspace/WORLD).read_bytes())['mipSizes']
    if label=='cooked':
        expected_mips={'cookedMipStackHeight':reduced*reduced*2,
            'cookedMipStackControl':reduced*reduced*2,
            'cookedMipStackColor':(reduced>>int(clip['colormapStartingMip'].text))**2*2}
        if mip_sizes!=expected_mips:
            raise ValueError('Cooked terrain mip sizes differ from measured native coarsest dimensions')
    path_value(world['environmentParameters'].find('object/properties/prop[@name="environmentDefinition"]'),ENV)
    path_value(props(LAYER,'CStaticMeshComponent')['mesh'],FLOOR)
    graph_prop=props(QUEST,'CQuest')['graph']
    graph=graph_prop.find('reference')
    if graph is None: graph=graph_prop.find('object')
    if graph is None or graph.get('class')!='CQuestGraph': raise ValueError('Native quest graph is NULL')
    blocks=props(QUEST,'CQuestGraph',graph.get('id'))['graphBlocks'].find('array')
    if stock_bootstrap:
        # Exact native control quest already observed advancing retail gameplay.
        # This is a diagnostic comparison, not the final minimal studio quest.
        expected=['CQuestPhaseBlock','CQuestLayersHiderBlock','CQuestPhaseBlock',
            'CQuestPhaseBlock','CQuestFactsDBChangingBlock','CQuestFactsDBChangingBlock',
            'CQuestPhaseBlock','CQuestPhaseBlock','CQuestStoryPhaseSetterBlock',
            'CQuestStoryPhaseSetterBlock','CQuestFactsDBChangingBlock',
            'CQuestFactsDBChangingBlock','CQuestFactsDBChangingBlock',
            'CQuestStoryPhaseSetterBlock','CQuestStoryPhaseSetterBlock',
            'CQuestEndBlock','CQuestStartBlock']
        actual=[e[0].get('class') for e in blocks.findall('element')]
        if blocks.get('count')!='17' or actual!=expected:
            raise ValueError('Native stock control quest structure differs')
        if label=='cooked' and props(QUEST,'CQuestGraph',graph.get('id'))['sourceDataRemoved'].text!='true':
            raise ValueError('Cooked stock control quest source-data flag differs')
    else:
        if blocks.get('count') != '2':
            raise ValueError('Native studio quest requires Start and its lifetime block')
        start=blocks.find('element/reference')
        if start is None or start.get('class')!='CQuestStartBlock': raise ValueError('Native quest Start link missing')
        start_props=props(QUEST,'CQuestStartBlock',start.get('id'))
        pause=blocks.findall('element/reference')[1]
        if pause.get('class')!='CQuestPauseConditionBlock': raise ValueError('Native studio lifetime block missing')
        pause_props=props(QUEST,'CQuestPauseConditionBlock',pause.get('id'))
        if pause_props['forceKeepLoadingScreen'].text!='false': raise ValueError('Studio lifetime must not retain loading screen')
        delay=pause_props['conditions'].find('array/element/reference')
        if delay is None or delay.get('class')!='CQuestHiResRealtimeDelayCondition': raise ValueError('Native studio lifetime condition missing')
        delay_props=props(QUEST,'CQuestHiResRealtimeDelayCondition',delay.get('id'))
        if delay_props['seconds'].text!='86400' or delay_props['active'].text!='true': raise ValueError('Native studio lifetime condition differs')
        if label=='cooked':
            cached=start_props['cachedConnections'].find('array/element/object/properties/prop[@name="blocks"]/array')
            if cached is None or cached.get('count')!='1': raise ValueError('Cooked Start must reach the lifetime block')
            destination=cached.find('.//reference')
            if destination is None or destination.get('class')!='CQuestPauseConditionBlock' or destination.get('id')!=pause.get('id'):
                raise ValueError('Cooked Start reaches a different block')
            if props(QUEST,'CQuestGraph',graph.get('id'))['sourceDataRemoved'].text!='true':
                raise ValueError('Cooked lifetime graph source-data flag differs')
    result=dict(schema='malemod.iteration-native-links/1',label=label,
        resources=[dict(path=p,sha256=digest(workspace/p),dumpSHA256=digest(job/('readback-'+label)/(Path(p).name+'.xml'))) for p in dumps],
        nonNullWorldPlayerCameraQuestFloorEnvironment=True,nonNullTerrainClipMap=True,
        nativeTileTopology=[TERRAIN_TILE],nativeMipSizes=mip_sizes,
        nativeResolutionDerivation=dict(total=total,clipSize=size,levels=expected_levels,coarsest=reduced),
        commands=commands,bootstrapMode='stock-q002-control' if stock_bootstrap else 'minimal-lifetime')
    result['nativeOcclusionDimensions']=dict(worldDimensions=world_dimensions,
        tileSize=256,tilesPerEdge=occlusion_tiles,
        nativeRule='iWorldDimensions % iTileSize == 0',
        sdkSymbol='CWorld::InitializeOcclusionCulling',sdkAddress='0x1428c2150')
    if label == 'cooked':
        result['nativeLayerOwnership'] = inspect_layers((workspace / WORLD).read_bytes(), LAYER)
    write_json(job/('native-links-'+label+'.json'),result)
    return result


def author(contract, native_layer_structure=False):
    extent = contract['floor']['extentMeters']
    thickness = contract['floor']['thicknessMeters']
    layer = resource([
        ('CLayer #0', '', {'entities': array('array:33,0,ptr:CEntity', [reference('ptr:CEntity', 'CEntity #1')]),
                          'nameCount': scalar('Uint32', 1)}),
        ('CEntity #1', 'CLayer #0', {'name': scalar('String', 'Iteration floor'), 'guid': guid('floor'),
            # Keep the single studio collider directly inspectable instead of
            # extracting it into an opaque streamingDataBuffer on native resave.
            'entityStaticFlags': scalar('EEntityStaticFlags','ESF_NoCompExtract'),
            'transform': transform((0, 0, -thickness/2)),
            'Components': array('array:0,0,ptr:CComponent', [reference('ptr:CComponent', 'CStaticMeshComponent #2')])}),
        ('CStaticMeshComponent #2', 'CEntity #1', {'name': scalar('String', 'floor'), 'guid': guid('floor-mesh'),
            'transform': transform(scale=(extent, extent, thickness)),
            'mesh': external('handle:CMesh', FLOOR, 'CMesh', True)})])
    world = resource([
        ('CGameWorld #0', '', {'worldDimensions': scalar('Float', WORLD_DIMENSIONS),
            'terrainClipMap': reference('ptr:CClipMap','CClipMap #4'),
            'startupCameraPosition': vector('Vector', (0, -3, 1.5, 1)),
            'pathLib': reference('ptr:CPathLibWorld', 'CPathLibWorld #3'),
            'environmentParameters': {'_type': 'SWorldEnvironmentParameters', '_vars': {
                'environmentDefinition': external('handle:CEnvironmentDefinition',
                    ENV,
                    'CEnvironmentDefinition', True)}},
            'newLayerGroupFormat': scalar('Bool', False), 'hasEmbeddedLayerInfos': scalar('Bool', True),
            'Firstlayer': handle('CLayerGroup', 'CLayerGroup #1')}),
        ('CLayerGroup #1', 'CGameWorld #0', {'name': scalar('String', 'malemod_iteration'),
            'depotPath': scalar('String', 'levels\\malemod_iteration'),
            'isVisibleOnStart': scalar('Bool', True), 'hasEmbeddedLayerInfos': scalar('Bool', True),
            'Worldhandle': handle('CGameWorld', 'CGameWorld #0'),
            'Layergrouphandle': handle('CLayerGroup', 'NULL'),
            'ChildrenGroups': array('CBufferVLQInt32:CHandle:CLayerGroup', []),
            'ChildrenInfos': array('CBufferVLQInt32:CHandle:CLayerInfo', [handle('CLayerInfo', 'CLayerInfo #2')])}),
        ('CLayerInfo #2', 'CLayerGroup #1', {'depotFilePath': scalar('String', LAYER.replace('/', '\\')),
            'shortName': scalar('String', 'floor'), 'guid': guid('floor-layer'),
            'streamingLayer': scalar('Bool', False), 'hasEmbeddedLayerInfo': scalar('Bool', True),
            'ParentGroup': handle('CLayerGroup', 'CLayerGroup #1')}),
        ('CPathLibWorld #3', 'CGameWorld #0', {}),
        # Native StartGame unconditionally toggles the world's CClipMap. These
        # CClipMap::Reinit derives levels by halving total resolution until it
        # reaches clipSize, whose native minimum is256. Copying the reference
        # world's four levels into a one-tile world was inconsistent.
        ('CClipMap #4','CGameWorld #0',{
            'clipSize':scalar('Uint32',256),'clipmapSize':scalar('Uint32',1024),
            'tileRes':scalar('Uint32',1024),'numClipmapStackLevels':scalar('Uint32',2),
            'colormapStartingMip':scalar('Int32',1),'numTilesPerEdge':scalar('Uint32',1),
            'terrainSize':scalar('Float',128),'terrainCorner':vector('Vector',(-64,-64,0,1)),
            # Exact donor terrain height encoding is translated150 native world
            # units downward, so it remains below the separate floor at zero.
            'lowestElevation':scalar('Float',-200),'highestElevation':scalar('Float',-50),
            'material':external('handle:IMaterial',TERRAIN_MATERIAL,'CMaterialGraph',True),
            'tileHeightRanges':array('array:2,0,Vector2',[{'_type':'Vector2','_vars':{'X':scalar('Float',-144.99886),'Y':scalar('Float',-125.0011)}}]),
            'minWaterHeight':array('array:2,0,Float',[scalar('Float',-150)]),
            'TerrainTiles':array('array:0,0,handle:CTerrainTile',[external('handle:CTerrainTile',TERRAIN_TILE,'CTerrainTile',True)])})])
    if native_layer_structure:
        # SDK CWorld::OnCook calls EnumerateLayersStructure when m_worldLayers
        # is NULL, populates a native root from this resource's actual directory,
        # then serializes that root. Do not hand-write its lifetime/parent tail.
        # These are the measured uncooked SDK reference-world flags, not a
        # retrofit that relabels an existing embedded legacy group.
        fields = world['_chunks']['CGameWorld #0']['_vars']
        fields['newLayerGroupFormat'] = scalar('Bool', True)
        fields['hasEmbeddedLayerInfos'] = scalar('Bool', False)
        del fields['Firstlayer']
        del world['_chunks']['CLayerGroup #1']
        del world['_chunks']['CLayerInfo #2']
    # Native schema measured from the SDK reference_level_test.w2quest dump.
    # Keep a real main-quest thread alive while the studio is in use. A bare
    # Start with no outgoing block otherwise finishes immediately.
    # The measured SDK delay condition creates no campaign/NPC/cinematic work.
    quest = resource([
        ('CQuest #0', '', {'graph': reference('ptr:CQuestGraph', 'CQuestGraph #1')}),
        ('CQuestGraph #1', 'CQuest #0', {'graphBlocks': array('array:2,0,ptr:CGraphBlock',
            [reference('ptr:CGraphBlock', 'CQuestStartBlock #2'),
             reference('ptr:CGraphBlock', 'CQuestPauseConditionBlock #4')]), 'isTest': scalar('Bool',False)}),
        ('CQuestStartBlock #2','CQuestGraph #1', {'name':scalar('String','Start'),
            'guid':guid('quest-start'), 'position':vector('Vector',(0,0,0,1)),
            'sockets':array('array:2,0,ptr:CGraphSocket',[reference('ptr:CGraphSocket','CQuestGraphSocket #3')])}),
        ('CQuestGraphSocket #3','CQuestStartBlock #2', {'block':reference('ptr:CGraphBlock','CQuestStartBlock #2'),
            'name':scalar('CName',' '),'flags':scalar('Uint32',110),
            'direction':scalar('ELinkedSocketDirection','LSD_Output'),
            'placement':scalar('ELinkedSocketPlacement','LSP_Right'),
            'drawStyle':scalar('ELinkedSocketDrawStyle','LSDS_Default'),
            'connections':array('array:2,0,ptr:CGraphConnection',[reference('ptr:CGraphConnection','CGraphConnection #8')])}),
        ('CQuestPauseConditionBlock #4','CQuestGraph #1', {
            'name':scalar('String','Isolated studio lifetime'), 'guid':guid('studio-lifetime'),
            'position':vector('Vector',(200,0,0,1)), 'forceKeepLoadingScreen':scalar('Bool',False),
            'conditions':array('array:2,0,ptr:IQuestCondition',[reference('ptr:IQuestCondition','CQuestHiResRealtimeDelayCondition #7')]),
            'sockets':array('array:2,0,ptr:CGraphSocket',[reference('ptr:CGraphSocket','CQuestGraphSocket #5'),reference('ptr:CGraphSocket','CQuestGraphSocket #6')])}),
        ('CQuestGraphSocket #5','CQuestPauseConditionBlock #4', {
            'block':reference('ptr:CGraphBlock','CQuestPauseConditionBlock #4'),
            'name':scalar('CName','In'),'flags':scalar('Uint32',111),
            'direction':scalar('ELinkedSocketDirection','LSD_Input'),
            'placement':scalar('ELinkedSocketPlacement','LSP_Left'),
            'connections':array('array:2,0,ptr:CGraphConnection',[reference('ptr:CGraphConnection','CGraphConnection #8')])}),
        ('CQuestGraphSocket #6','CQuestPauseConditionBlock #4', {
            'block':reference('ptr:CGraphBlock','CQuestPauseConditionBlock #4'),
            'name':scalar('CName','Out'),'flags':scalar('Uint32',110),
            'direction':scalar('ELinkedSocketDirection','LSD_Output'),
            'placement':scalar('ELinkedSocketPlacement','LSP_Right'),
            'connections':array('array:2,0,ptr:CGraphConnection',[])}),
        ('CQuestHiResRealtimeDelayCondition #7','CQuestPauseConditionBlock #4', {
            'active':scalar('Bool',True),'seconds':scalar('Uint32',86400)}),
        ('CGraphConnection #8','CQuestGraph #1', {
            'source':reference('ptr:CGraphSocket','CQuestGraphSocket #3'),
            'destination':reference('ptr:CGraphSocket','CQuestGraphSocket #5'),
            'inactive':scalar('Bool',False)})])
    game = resource([('CWitcherGameResource #0', '', {
        'worlds': array('array:2,0,SWorldDescription', [{'_type': 'SWorldDescription', '_vars': {
            'world': external('soft:CWorld', WORLD, 'CGameWorld')}}]),
        'defaultPlayerTemplate': external('soft:CEntityTemplate', 'gameplay/templates/characters/player/player.w2ent', 'CEntityTemplate'),
        'defaultCameraTemplate': external('soft:CEntityTemplate', 'gameplay/camera/new_camera.w2ent', 'CEntityTemplate'),
        'mainQuest': external('soft:CQuest',QUEST,'CQuest'),
        # The official new-world tutorial explicitly requires the stock map
        # configuration. The canonical game defines this one Quest pin type.
        'mapPinConfig':{'_type':'SMapPinConfig','_vars':{
            'pinTypes':array('array:2,0,SMapPinType',[{'_type':'SMapPinType','_vars':{
                'typeName':scalar('CName','Quest'),'icon':scalar('String',''),
                'radius':scalar('Float',0),'color':{'_type':'Color','_vars':{
                    n:scalar('Uint8',0) for n in ('Red','Green','Blue','Alpha')}}}}])}},
        'huntingClueCategoryResource':external('soft:C2dArray','game/hunting_clues_enums.csv','C2dArray'),
        'startingPoint': transform(contract['spawnMeters']),
        'newGameLoadingVideo': scalar('String', '')})])
    return {WORLD: world, LAYER: layer, GAME: game, QUEST:quest}


def write_native_package_proof(package, job, report):
    """Bind the separate native reference readback to this exact packed build."""
    if not report['cookedNativeLinks']['nonNullWorldPlayerCameraQuestFloorEnvironment'] or not report['cookedNativeLinks'].get('nonNullTerrainClipMap'):
        raise ValueError('Native iteration references are not certified')
    proof=dict(schema='malemod.iteration-native-package/2',
        buildManifestSHA256=digest(package/'build-manifest.json'),
        authoringReceipt=str(job/'authoring.json'),authoringReceiptSHA256=digest(job/'authoring.json'),
        nativeLinksReceipt=str(job/'native-links-cooked.json'),
        nativeLinksReceiptSHA256=digest(job/'native-links-cooked.json'),
        observedGameplay=False)
    write_json(package.with_name(package.name+'.iteration-native-proof.json'),proof)


def prepare(native=False, cook=False, stock_bootstrap=False, native_layer_structure=False):
    cfg = settings()
    cfg['depot'] = cfg['redkit']/'r4data'
    contract_path = cfg['base']/'profiles/iteration-sandbox.json'
    contract = json.loads(contract_path.read_text())
    validate_world_dimensions(WORLD_DIMENSIONS)
    if contract['schema'] != 'malemod.iteration-sandbox/1':
        raise ValueError('Unrecognized shared scene contract')
    # A task-owned build junction can put large SDK caches on E: while retaining
    # the adapter's existing owned-build path checks and no-space WCC paths.
    storage = ROOT/'build/iteration-storage'
    if not storage.is_dir():
        raise RuntimeError('Configure build/iteration-storage to a volume with enough native cook space')
    job = storage/('world-'+uuid.uuid4().hex[:12])
    workspace = job/'workspace'; workspace.mkdir(parents=True)
    converter = ROOT/'build/research/wkit-current/MaleModCR2W.exe'
    bridge=json.loads((converter.parent/'toolchain.json').read_text())
    if digest(converter)!=bridge['executableSHA256'] or digest(converter.parent/'WolvenKit.CR2W.dll')!=bridge['librarySHA256']:
        raise ValueError('Original authoring converter differs')
    records = []
    for path, data in author(contract, native_layer_structure).items():
        source = job/(Path(path).name+'.json'); write_json(source, data)
        output = workspace/path; output.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([str(converter), 'import', str(source), str(output)], capture_output=True, text=True)
        (job/(Path(path).name+'.writer.log')).write_text(result.stdout+result.stderr)
        if result.returncode or not output.is_file() or '[DewalkNode]' in result.stdout or 'NULL chunk' in result.stdout:
            raise RuntimeError('Authoring conversion failed; inspect '+str(job))
        records.append({'path': path, 'sourceSHA256': digest(source), 'nativeSHA256': digest(output)})
    bootstrap_source=cfg['redkit']/'r4data'/STOCK_BOOTSTRAP
    if stock_bootstrap:
        shutil.copy2(bootstrap_source,workspace/QUEST)
        records[-1]=dict(path=QUEST,sourcePath=str(bootstrap_source),
            sourceSHA256=digest(bootstrap_source),nativeSHA256=digest(workspace/QUEST),
            nativeBytesCopiedExactly=True)
    stock = cfg['redkit']/'r4data/engine/meshes/editor/box.w2mesh'
    floor = workspace/FLOOR; shutil.copy2(stock, floor)
    environment = cfg['redkit']/'r4data'/ENV_SOURCE
    shutil.copy2(environment, workspace/ENV)
    terrain_material=cfg['redkit']/'r4data/engine/reference_level/world/terrain_material.w2mg'
    shutil.copy2(terrain_material,workspace/TERRAIN_MATERIAL)
    terrain_tile=cfg['redkit']/'r4data'/TERRAIN_TILE_SOURCE
    (workspace/TERRAIN_TILE).parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(terrain_tile,workspace/TERRAIN_TILE)
    physical_mapping=terrain_physical_map(cfg,workspace)
    report = dict(schema='malemod.iteration-world-authoring/1', contractSHA256=digest(contract_path),
        converterSHA256=digest(converter), resources=records,
        bootstrapMode='stock-q002-control' if stock_bootstrap else 'minimal-lifetime',
        layerStructureMode='native-directory-population' if native_layer_structure else 'legacy-embedded-control',
        floorSource=str(stock), floorSourceSHA256=digest(stock),
        environmentSource=str(environment), environmentSourceSHA256=digest(environment),
        terrainMaterialSource=str(terrain_material),terrainMaterialSourceSHA256=digest(terrain_material),
        terrainTileSource=str(terrain_tile),terrainTileSourceSHA256=digest(terrain_tile),
        terrainPhysicalMapping=physical_mapping,
        terrainResolutionDerivation=dict(clipSize=256,totalResolution=1024,levels=2,
            nativeRule='CClipMap::Reinit halves total until <=clipSize; power-of-two clipSize>=256',
            sdkSymbol='CClipMap::Reinit(SClipmapParameters const&)',sdkAddress='0x142af32b0',
            diagnosticDisassemblySHA256=digest(Path('E:/MaleModBuilds/isolation-capability/clipmap-init-sdk.txt'))),
        terrainTileLineage=dict(originalTileCoordinates=[0,0],originalTileResolution=1024,
            originalElevationRange=[-50,100],ownedElevationRange=[-200,-50],
            verticalTranslation=-150,nativeTileBytesUnchanged=True),
        bootstrapDefaultsSource='game/witcher3.redgame',
        bootstrapDefaultsSourceSHA256=digest(cfg['redkit']/'r4data/game/witcher3.redgame'),
        installed=False, observedGameplay=False, native=[])
    write_json(job/'authoring.json', report)
    if native or cook:
        # Scoped solely to our owned level path; never resave the SDK/depot.
        command = run_wcc(cfg, 'resave', ['-tmpdir='+str(job/'resave-tmp'),
            '-path=levels\\malemod_iteration', '-nosourcecontrol', '-ignorefileversion'], workspace, 'iteration-world-resave')
        report['native'].append(command)
        depot = Path(command['args'][command['args'].index('-uncookDir')+1])
        for path in [WORLD, LAYER, GAME, QUEST, FLOOR, ENV,TERRAIN_MATERIAL,TERRAIN_TILE]:
            output = depot/path
            if not output.is_file(): raise RuntimeError('Missing native resave: '+path)
            shutil.copy2(output, workspace/path)
        report['resavedResources'] = [{'path': p, 'sha256': digest(workspace/p)} for p in [WORLD, LAYER, GAME, QUEST, FLOOR, ENV]]
        report['nativeLinks']=verify_native_links(cfg,workspace,job,'resaved',stock_bootstrap,existing_depot=depot)
        write_json(job/'authoring.json', report)
    if cook:
        package = build(cfg, {'name': 'modMaleModIteration', 'version': '0.1.0', 'platform': 'pc',
            'cacheBuilders': ['physics'], 'reuseReadOnlyDepot': True,
            'scope': 'Separate native iteration world; gameplay unverified'}, workspace)
        manifest=json.loads((package/'build-manifest.json').read_text())
        pack=next(c for c in manifest['nativeCommands'] if c['command']=='pack')
        packed_input=Path(next(a[5:] for a in pack['args'] if a.startswith('-dir=')))
        report['cookedNativeLinks']=verify_native_links(cfg,packed_input,job,'cooked',stock_bootstrap)
        report['package'] = str(package)
        write_json(job/'authoring.json', report)
        write_native_package_proof(package,job,report)
    print(job)
    return job


def resume_cook(job, native_resume=None):
    """Continue a hash-bound resaved intake; never reauthor or resave it."""
    job = Path(job).absolute()
    if not job.resolve().is_relative_to((ROOT / 'build/iteration-storage').resolve()):
        raise ValueError('Resume job must be owned iteration storage')
    report_path = job / 'authoring.json'
    report = json.loads(report_path.read_text())
    if report.get('package') or report.get('installed') or report.get('observedGameplay'):
        raise ValueError('Resume requires an unpublished, uninstalled native intake')
    workspace = job / 'workspace'
    native = report['nativeLinks']
    if native.get('label') != 'resaved' or not native.get('nonNullWorldPlayerCameraQuestFloorEnvironment'):
        raise ValueError('Resume requires successful native resave/readback')
    for record in native['resources'] + report['resavedResources']:
        if digest(workspace / record['path']) != record['sha256']:
            raise ValueError('Resaved intake changed: ' + record['path'])
    intake_args = native['commands'][0]['args']
    resaved_view = Path(intake_args[intake_args.index('-uncookDir') + 1])
    validate_readonly_depot('dumpfile', workspace, resaved_view)
    cfg = settings()
    cfg['depot'] = cfg['redkit'] / 'r4data'
    recipe = dict(name='modMaleModIteration', version='0.1.0', platform='pc',
                  cacheBuilders=['physics'], reuseReadOnlyDepot=True,
                  scope='Separate native iteration world; gameplay unverified')
    continuation = dict(schema='malemod.iteration-cook-continuation/1',
                        authoringReceiptSHA256=digest(report_path),
                        nativeLinksReceiptSHA256=digest(job / 'native-links-resaved.json'),
                        workspace=str(workspace), recipe=recipe,
                        nativeResavedView=str(resaved_view),
                        files=[dict(path=p.relative_to(workspace).as_posix(), sha256=digest(p))
                               for p in sorted(workspace.rglob('*'))
                               if p.is_file() and p.suffix not in ('.db', '.db-shm', '.db-wal')],
                        installed=False, observedGameplay=False)
    if native_resume is None:
        write_json(job / 'continuation-recipe.json', continuation)
    else:
        prior = json.loads((job / 'continuation-recipe.json').read_text())
        if prior != continuation:
            raise ValueError('Recorded intake/recipe differs from successful cook continuation')
    package = build(cfg, recipe, workspace, native_resume=native_resume)
    manifest = json.loads((package / 'build-manifest.json').read_text())
    pack = next(c for c in manifest['nativeCommands'] if c['command'] == 'pack')
    packed_input = Path(next(a[5:] for a in pack['args'] if a.startswith('-dir=')))
    report['cookedNativeLinks'] = verify_native_links(cfg, packed_input, job, 'cooked',
        report['bootstrapMode'] == 'stock-q002-control')
    report['package'] = str(package)
    report['continuationReceiptSHA256'] = digest(job / 'continuation-recipe.json')
    write_json(report_path, report)
    write_native_package_proof(package, job, report)
    print(package)
    return package


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--cook', action='store_true')
    parser.add_argument('--stock-bootstrap-control',action='store_true',
        help='Diagnostic only: exact observed stock quest with own native scene')
    parser.add_argument('--native-layer-structure', action='store_true',
        help='Diagnostic: let REDkit populate native layer ownership from the owned folder')
    parser.add_argument('--resume-cook', type=Path,
        help='Continue a previously resaved/read-back owned intake, without reauthoring')
    parser.add_argument('--resume-native-receipt', type=Path,
        help='Continue downstream stages from a hash-bound successful cook, without recooking')
    args = parser.parse_args()
    if args.resume_native_receipt and not args.resume_cook:
        parser.error('A native continuation requires its recorded --resume-cook job')
    if args.resume_cook:
        if args.native or args.cook or args.stock_bootstrap_control or args.native_layer_structure:
            parser.error('Resume consumes the recorded recipe; do not mix new authoring flags')
        resume_cook(args.resume_cook, args.resume_native_receipt)
    else:
        prepare(args.native, args.cook, args.stock_bootstrap_control, args.native_layer_structure)
