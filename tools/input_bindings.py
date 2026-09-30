"""Add/remove only MaleMod's hotkeys, preserving all unrelated input settings."""
from pathlib import Path
import time,uuid
from mod import ROOT,digest,write_json,read_json

CONTEXTS=('Exploration','Combat','Horse','Boat')
BINDINGS={'IK_F6':'MaleModToggle','IK_Up':'MaleModPrevious','IK_Down':'MaleModNext',
          'IK_Left':'MaleModDecrease','IK_Right':'MaleModIncrease','IK_F8':'MaleModReset'}

def edit_bindings(data,remove=False):
    encoding='utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig' if data.startswith(b'\xef\xbb\xbf') else 'utf-8'
    text=data.decode(encoding);newline='\r\n' if '\r\n' in text else '\n'
    lines=text.splitlines(keepends=True);output=[];section=None;seen=set();changed=[]
    additions=[key+'=(Action='+action+')' for key,action in BINDINGS.items()]
    def finish():
        if section not in CONTEXTS:return
        seen.add(section)
        if not remove:
            existing={x.strip() for x in output[section_start:]}
            for key,action in BINDINGS.items():
                conflict=[x for x in existing if x.startswith(key+'=') and x!=key+'=(Action='+action+')']
                if conflict:raise ValueError('Hotkey '+key+' already has an action in '+section)
            if output and not output[-1].endswith(('\r','\n')):output[-1]+=newline
            for line in additions:
                if line not in existing:output.append(line+newline);changed.append([section,line])
    section_start=0
    for line in lines:
        stripped=line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            finish();section=stripped[1:-1];section_start=len(output)
        if remove and section in CONTEXTS and stripped in additions:
            changed.append([section,stripped]);continue
        output.append(line)
    finish()
    if not remove and seen!=set(CONTEXTS):raise ValueError('Missing native input contexts: '+str(set(CONTEXTS)-seen))
    return ''.join(output).encode(encoding),changed

def install(path):
    path=Path(path).resolve();before=path.read_bytes();after,changes=edit_bindings(before)
    if not changes:return {'path':str(path),'alreadyPresent':True,'sha256':digest(path)}
    backup=ROOT/'local/input-backups'/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    backup.mkdir(parents=True);(backup/'input.settings').write_bytes(before)
    if path.read_bytes()!=before:raise RuntimeError('Input settings changed during preparation')
    staging=path.with_name('input.settings.malemod-'+uuid.uuid4().hex[:6]);staging.write_bytes(after);staging.replace(path)
    receipt={'path':str(path),'backup':str(backup/'input.settings'),'beforeSHA256':digest(backup/'input.settings'),
             'afterSHA256':digest(path),'inserted':changes}
    write_json(ROOT/'local/input-bindings.json',receipt);return receipt

def uninstall():
    receipt=read_json(ROOT/'local/input-bindings.json');path=Path(receipt['path'])
    before=path.read_bytes();after,changes=edit_bindings(before,remove=True)
    if path.read_bytes()!=before:raise RuntimeError('Input settings changed during removal')
    staging=path.with_name('input.settings.malemod-'+uuid.uuid4().hex[:6]);staging.write_bytes(after);staging.replace(path)
    return changes
