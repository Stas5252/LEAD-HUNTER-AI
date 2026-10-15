#!/usr/bin/env python3
"""Rights registry and deterministic local FFmpeg/Pillow production; no paid API."""
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile,textwrap,uuid
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

MAX_FILE=45_000_000
FONT=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def root_dirs(root):
 root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
 for d in ('assets','manifests','renders'):
  target=root/d
  if target.is_symlink():raise ValueError('Symlink media directory')
  target.mkdir(exist_ok=True)
 return root

def confined(path,root):
 p=Path(path)
 if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Path outside media root')
 for parent in p.parents:
  if parent==root:break
  if parent.is_symlink():raise ValueError('Symlink path')
 return p.resolve()

def register_asset(path,rights,root):
 root=root_dirs(root);path=confined(path,root)
 if rights.get('kind') not in ('own','licensed','public_domain') or not rights.get('grant'):raise ValueError('Explicit own/license grant required; reference is not a license')
 if rights['kind']=='licensed' and (not rights.get('license_url') or rights.get('commercial') is not True or rights.get('derivatives') is not True):raise ValueError('License must permit commercial derivatives')
 if not path.is_file() or path.stat().st_size>MAX_FILE:raise ValueError('File missing/too large')
 ext=path.suffix.lower()
 if not re.fullmatch(r'\.[a-z0-9]{1,8}',ext):raise ValueError('Invalid file extension')
 identity=digest(path);dest=root/'assets'/(identity+ext)
 if dest.is_symlink():raise ValueError('Symlink destination')
 if not dest.exists():
  temp=dest.with_name(dest.name+'.'+uuid.uuid4().hex+'.tmp');shutil.copyfile(path,temp);os.replace(temp,dest)
 manifest={'asset_id':identity,'path':'assets/'+dest.name,'sha256':identity,'bytes':dest.stat().st_size,'rights':rights,'is_demo':rights.get('is_demo') is True}
 target=root/'manifests'/(identity+'.json')
 if target.is_symlink():raise ValueError('Symlink manifest')
 if target.exists():return json.loads(target.read_text())
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(manifest,f,ensure_ascii=False)
 return manifest

def resolve_asset(asset_id,root):
 if not re.fullmatch(r'[a-f0-9]{64}',asset_id):raise ValueError('Invalid asset ID')
 root=root_dirs(root);target=confined(root/'manifests'/(asset_id+'.json'),root)
 if not target.is_file():raise ValueError('Unknown asset')
 d=json.loads(target.read_text());p=confined(root/d['path'],root)
 if d['asset_id']!=asset_id or d['sha256']!=asset_id or p.stat().st_size>MAX_FILE or digest(p)!=asset_id:raise ValueError('Asset changed; approval invalid')
 if d.get('rights',{}).get('kind') not in ('own','licensed','public_domain'):raise ValueError('Rights missing')
 return p

def run(args,timeout=180):
 try:subprocess.run(args,check=True,timeout=timeout,capture_output=True)
 except (subprocess.CalledProcessError,subprocess.TimeoutExpired):raise ValueError('Media tool failed; no output accepted') from None

def font(size):
 if not FONT.is_file():raise ValueError('Install fonts-dejavu-core for Cyrillic rendering')
 return ImageFont.truetype(str(FONT),size)

def card_image(title,text,cta,size=(1080,1350),demo=False):
 for value in (title,text,cta):
  if not isinstance(value,str) or len(value)>700:raise ValueError('Card text limit')
 im=Image.new('RGB',size,'#101b2a');draw=ImageDraw.Draw(im);scale=size[0]/1080
 def paint(value,y,sz,width,color):
  f=font(int(sz*scale));lines=[]
  for paragraph in value.splitlines() or ['']:
   lines.extend(textwrap.wrap(paragraph,width=width) or [''])
  for line in lines:
   if y>size[1]-110*scale:raise ValueError('Text does not fit card; shorten it')
   draw.text((70*scale,y),line,font=f,fill=color);y+=(sz+20)*scale
  return y
 paint(('DEMO · ' if demo else '')+title,100*scale,44,32,'#69d6ca')
 paint(text,300*scale,56,27,'white')
 paint(cta,size[1]-180*scale,32,42,'#69d6ca')
 return im

def render_carousel(spec,root):
 root=root_dirs(root);cards=spec.get('cards',[])
 if not isinstance(cards,list) or not 5<=len(cards)<=7:raise ValueError('Carousel requires 5–7 cards')
 folder=root/'renders'/uuid.uuid4().hex;folder.mkdir();assets=[]
 for n,text in enumerate(cards,1):
  path=folder/f'card-{n}.png';card_image(spec.get('title',''),text,spec.get('cta','stanislavweb.ru'),demo=spec.get('is_demo') is True).save(path)
  assets.append(register_asset(path,{'kind':'own','grant':'Local text/graphic composition; source text confirmed by owner','is_demo':spec.get('is_demo') is True},root))
 return {'type':'carousel','assets':assets,'spec':spec}

def synthetic_demo(root):
 root=root_dirs(root);path=root/'renders'/('synthetic-'+uuid.uuid4().hex+'.mp4')
 run(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi','-i','testsrc2=size=720x1280:rate=24','-t','2','-an','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p',str(path)])
 return register_asset(path,{'kind':'own','grant':'Synthetic FFmpeg test pattern, no third party assets','is_demo':True},root)

def has_demo(ids,root,seen=None):
 seen=set() if seen is None else seen
 for asset in ids:
  if asset in seen:continue
  seen.add(asset);resolve_asset(asset,root)
  m=json.loads((Path(root)/'manifests'/(asset+'.json')).read_text())
  if m.get('is_demo') is True or has_demo(m.get('rights',{}).get('dependencies',[]),root,seen):return True
 return False

def render_video(spec,root):
 root=root_dirs(root);scenes=spec.get('scenes',[])
 if not isinstance(scenes,list) or not 1<=len(scenes)<=12:raise ValueError('1–12 scenes required')
 durations=[v.get('seconds',3) for v in scenes]
 if any(not isinstance(v,(int,float)) or not 0.5<=v<=15 for v in durations) or sum(durations)>60:raise ValueError('Video duration limit 60s')
 folder=root/'renders'/uuid.uuid4().hex;folder.mkdir();segments=[];dependencies=[]
 demo=spec.get('is_demo') is True or has_demo([x['asset_id'] for x in scenes]+([spec['audio_asset_id']] if spec.get('audio_asset_id') else []),root)
 for n,(scene,seconds) in enumerate(zip(scenes,durations)):
  src=resolve_asset(scene['asset_id'],root)
  if src.suffix.lower() not in ('.mp4','.mov','.mkv','.webm','.png','.jpg','.jpeg'):raise ValueError('Unsupported video/image input')
  dependencies.append(scene['asset_id']);overlay=folder/f'overlay-{n}.png'
  # Text is rendered as an image. It never becomes an FFmpeg expression, path, or command.
  im=Image.new('RGBA',(720,1280),(0,0,0,0));d=ImageDraw.Draw(im);d.rectangle((0,850,720,1280),fill=(8,20,32,225))
  caption=('DEMO: ' if demo else '')+str(scene.get('caption',''))
  if len(caption)>180 or len(spec.get('cta',''))>80:raise ValueError('Caption/CTA limit')
  y=900
  for line in textwrap.wrap(caption,width=28):d.text((35,y),line,font=font(38),fill='white');y+=52
  d.text((35,1190),spec.get('cta','stanislavweb.ru'),font=font(28),fill='#69d6ca');im.save(overlay)
  out=folder/f'segment-{n}.mp4';segments.append(out)
  run(['ffmpeg','-v','error','-nostdin','-y','-protocol_whitelist','file,pipe','-stream_loop','-1','-i',str(src),'-loop','1','-i',str(overlay),
   '-filter_complex_threads','1','-filter_complex','[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=24[base];[base][1:v]overlay=0:0[v]',
   '-map','[v]','-t',str(seconds),'-an','-c:v','libx264','-threads','1','-preset','veryfast','-crf','24','-pix_fmt','yuv420p',str(out)])
 listing=folder/'segments.txt';listing.write_text(''.join("file '"+p.name+"'\n" for p in segments))
 output=folder/'result.mp4'
 run(['ffmpeg','-v','error','-nostdin','-y','-protocol_whitelist','file,pipe','-f','concat','-safe','1','-i',str(listing),'-c','copy','-movflags','+faststart',str(output)])
 # Narration is accepted only as a registered own/licensed audio asset.
 if spec.get('audio_asset_id'):
  audio=resolve_asset(spec['audio_asset_id'],root)
  if audio.suffix.lower() not in ('.wav','.mp3','.m4a','.ogg'):raise ValueError('Unsupported audio')
  narrated=folder/'narrated.mp4';dependencies.append(spec['audio_asset_id'])
  run(['ffmpeg','-v','error','-nostdin','-y','-protocol_whitelist','file,pipe','-i',str(output),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-t',str(sum(durations)),'-movflags','+faststart',str(narrated)]);output=narrated
 run(['ffmpeg','-v','error','-nostdin','-protocol_whitelist','file,pipe','-i',str(output),'-f','null','-'],timeout=90)
 return register_asset(output,{'kind':'own','grant':'Local montage with new scene sequence, captions and CTA; dependent assets retain their rights','dependencies':dependencies,'is_demo':demo},root)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='media');s=p.add_subparsers(dest='cmd',required=True)
 c=s.add_parser('register');c.add_argument('file');c.add_argument('rights_json')
 for name in ('video','carousel'):
  c=s.add_parser(name);c.add_argument('spec_json')
 s.add_parser('demo');a=p.parse_args();root=Path(a.root)
 if a.cmd=='register':result=register_asset(Path(a.file),json.loads(Path(a.rights_json).read_text()),root)
 elif a.cmd=='demo':
  src=synthetic_demo(root);result=render_video({'scenes':[{'asset_id':src['asset_id'],'seconds':2,'caption':'Понятный сайт. Удобная заявка.'}],'cta':'stanislavweb.ru','is_demo':True},root)
 else:result=(render_video if a.cmd=='video' else render_carousel)(json.loads(Path(a.spec_json).read_text()),root)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
