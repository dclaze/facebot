#!/usr/bin/env python3
"""Original procedural ghost animation. No downloaded artwork or model inference.
Requires numpy, Pillow and ffmpeg (or imageio_ffmpeg). See --help.
"""
import argparse, hashlib, json, math, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
ROOT=Path(__file__).resolve().parents[1]
TAU=math.tau
DURATION=12.0

def smooth(a,b,t):
    u=max(0.,min(1.,(t-a)/(b-a)))
    return u*u*(3-2*u)

def pulse(a,b,c,d,t):
    return smooth(a,b,t)*(1-smooth(c,d,t))

def bezier(a,b,c,d,n=70):
    u=np.linspace(0,1,n)[:,None]
    return (1-u)**3*np.array(a)+3*(1-u)**2*u*np.array(b)+3*(1-u)*u*u*np.array(c)+u**3*np.array(d)

def curve(draw,points,color,width):
    draw.line([tuple(p) for p in points],fill=color,width=width,joint='curve')

class Ghost:
    def __init__(self,width=720,height=1080,eyes_only=False):
        self.width,self.height,self.eyes_only=width,height,eyes_only
        # Work in a fixed 720x1080 design space, with a fit transform at export.
        self.rng=np.random.default_rng(2718)
        n=360
        self.y,self.x=np.mgrid[:n,:n].astype(np.float32)
        self.x=(self.x-n/2)/(n/2);self.y=(self.y-n/2)/(n/2)
        self.noise=self.rng.normal(0,.023,(n,n)).astype(np.float32)
        self.veins=[]
        for i in range(13):
            x=self.rng.uniform(18,340);y=self.rng.uniform(90,250)
            self.veins.append((x,y,self.rng.uniform(-.6,.6)))

    def iris(self,pupil,phase,mirror=False):
        x,y=self.x,self.y
        r=np.sqrt(x*x+y*y);angle=np.arctan2(y,x)
        # Layered radial fibres and branching furrows, fixed to the iris.
        fibres=(.18*np.sin(83*angle+12*r+1.3*np.sin(17*angle))+
                .13*np.sin(137*angle-19*r)+.08*np.sin(251*angle+31*r)+
                .07*np.sin(43*angle+29*r)+self.noise)
        rim=np.clip((1-r)*8,0,1)
        inner=np.exp(-((r-pupil-.12)/.14)**2)
        brightness=(.29+.39*inner+fibres)*rim
        brightness*=1-.35*np.clip(-y,0,1)
        rgb=np.stack([brightness*.30,brightness*.86,brightness*1.28],axis=-1)
        # The pupil has an organic, gently scalloped edge.
        edge=pupil+.008*np.sin(29*angle)+.004*np.sin(47*angle)
        opening=np.clip((r-edge)*85,0,1)
        rgb*=opening[:,:,None]
        rgb+=np.exp(-((r-edge-.015)/.018)**2)[:,:,None]*np.array([.07,.20,.27])
        rgb[r>1]=0
        img=Image.fromarray(np.uint8(np.clip(rgb*255,0,255)))
        d=ImageDraw.Draw(img)
        d.ellipse((125,110,151,127),fill=(142,221,241))
        d.ellipse((148,122,157,130),fill=(95,154,183))
        if mirror:img=img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        return img

    def eye(self,t,side,opening,gaze,pupil,threat):
        w,h=310,260
        xx,yy=np.meshgrid(np.arange(w),np.arange(h))
        sphere=np.clip(1-((xx-w*.5)/(w*.58))**2-((yy-h*.52)/(h*.75))**2,0,1)**.7
        shade=.25+.75*np.clip(yy/h,0,1)
        texture=sphere*shade
        rgb=np.stack((texture*17,texture*40,texture*60),axis=-1)
        eye=Image.fromarray(rgb.astype(np.uint8))
        d=ImageDraw.Draw(eye)
        for vx,vy,lean in self.veins:
            vx=vx/360*w
            pts=[(vx+math.sin(i*.7+vx)*3+i*lean,vy+i*2.1) for i in range(18)]
            d.line(pts,fill=(7,21,36),width=1)
        iris=self.iris(pupil,t,side<0).resize((181,181),Image.Resampling.LANCZOS)
        iris_mask=Image.new('L',(181,181));ImageDraw.Draw(iris_mask).ellipse((0,0,180,180),fill=255)
        ix=int(w/2-90+gaze[0]);iy=int(h/2-90+gaze[1])
        eye.paste(iris,(ix,iy),iris_mask)
        # Slanted inner corners and curved lower lids keep the silhouette organic.
        cy=133;tilt=-side*(6+18*threat)
        upper=bezier((13,cy-tilt),(80,cy-99*opening-tilt),(235,cy-105*opening+tilt),(299,cy+tilt))
        lower=bezier((299,cy+tilt),(245,cy+89*opening+tilt),(75,cy+79*opening-tilt),(13,cy-tilt))
        mask=Image.new('L',(w,h));md=ImageDraw.Draw(mask)
        md.polygon([tuple(p) for p in np.vstack((upper,lower))],fill=255)
        mask=mask.filter(ImageFilter.GaussianBlur(1.1))
        eye=ImageChops.multiply(eye,Image.merge('RGB',(mask,mask,mask)))
        lid=Image.new('RGB',(w,h));ld=ImageDraw.Draw(lid)
        curve(ld,upper,(11,38,51),4)
        curve(ld,lower,(25,78,99),2)
        eye=ImageChops.add(eye,lid)
        return eye

    def mouth(self,t,grin):
        layer=Image.new('RGB',(720,1080));d=ImageDraw.Draw(layer)
        if grin<.002:return layer
        x0,x1=188-26*grin,532+26*grin
        y0=665
        top=bezier((x0,y0),(280,711),(442,717),(x1,y0-8))
        bottom=bezier((x1,y0-8),(465,743+25*grin),(258,749+22*grin),(x0,y0))
        mask=Image.new('L',layer.size);md=ImageDraw.Draw(mask)
        md.polygon([tuple(p) for p in np.vstack((top,bottom))],fill=255)
        # Uneven translucent teeth, no copied mesh or image.
        teeth=Image.new('RGB',layer.size);td=ImageDraw.Draw(teeth)
        for i in range(12):
            x=176+i*31
            u=(x-360)/198
            baseline=703-36*u*u
            length=22+8*math.cos(i*1.91)+(10 if i in (2,9) else 0)
            td.polygon([(x,baseline-12),(x+24,baseline-12),(x+20,baseline+length),(x+7,baseline+length+4)],fill=(47,119,143))
            td.line([(x+3,baseline-7),(x+22,baseline-7)],fill=(99,184,201),width=2)
            td.polygon([(x+5,750),(x+25,750),(x+21,728-8*math.sin(i*2)),(x+10,731-8*math.sin(i*2))],fill=(30,77,100))
        teeth=ImageChops.multiply(teeth,Image.merge('RGB',(mask,mask,mask)))
        layer=ImageChops.add(layer,teeth);d=ImageDraw.Draw(layer)
        curve(d,top,(46,123,151),3);curve(d,bottom,(18,57,79),3)
        # Short creases at the mouth corners fade into the surrounding black.
        for side in [-1,1]:
            pts=bezier((360+side*194,666),(360+side*210,651),(360+side*216,641),(360+side*213,629))
            curve(d,pts,(13,40,52),2)
        return layer.point(lambda v:int(v*grin))

    def frame(self,t):
        t=t%DURATION
        threat=pulse(3.0,5.3,8.3,10.7,t)
        grin=pulse(4.1,6.0,8.0,10.5,t)
        blink=pulse(2.4,2.50,2.54,2.78,t)
        gaze_x=-16*pulse(.65,1.1,1.8,2.35,t)+21*pulse(8.3,8.8,9.7,10.4,t)
        gaze_y=-4*pulse(.65,1.1,1.8,2.35,t)
        opening=(1-.42*threat)*(1-.96*blink)
        pupil=.36-.12*threat+.016*math.sin(TAU*t/DURATION)
        layer=Image.new('RGB',(720,1080))
        drift=2.6*math.sin(TAU*t/DURATION)
        for side in [-1,1]:
            eye=self.eye(t,side,opening,(gaze_x,gaze_y),pupil,threat)
            x=48 if side<0 else 362
            y=int(342+drift+(2 if side>0 else 0))
            layer.paste(eye,(x,y))
        if not self.eyes_only:layer=ImageChops.add(layer,self.mouth(t,grin))
        # Bloom is light emitted by the original geometry, on a truly black field.
        small=layer.resize((180,270),Image.Resampling.BILINEAR)
        glow=small.filter(ImageFilter.GaussianBlur(4)).resize(layer.size,Image.Resampling.BILINEAR)
        layer=ImageChops.add(layer,glow,scale=1.0)
        layer=ImageChops.add(layer,layer.filter(ImageFilter.GaussianBlur(2.2)),scale=1.25)
        if (self.width,self.height)!=(720,1080):
            layer=layer.resize((self.width,self.height),Image.Resampling.LANCZOS)
        return layer

def encoder():
    found=shutil.which('ffmpeg')
    if found:return found
    try:
        import imageio_ffmpeg
    except ImportError:
        # Reuse the existing isolated local encoder, without installing globally.
        tools=ROOT/'.local/laughing-contest-tools'
        if tools.is_dir():sys.path.insert(0,str(tools))
        import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=ROOT/'content/animations/ghost-eyes')
    ap.add_argument('--eyes-only',action='store_true')
    ap.add_argument('--poster-only',action='store_true')
    ap.add_argument('--fps',type=int,default=24)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    if not 1<=args.fps<=60:ap.error('--fps must be between 1 and 60')
    g=Ghost(eyes_only=args.eyes_only)
    name='ghost-eyes-only' if args.eyes_only else 'ghost-face'
    for t,label in [(0,'watching'),(2.52,'blink'),(6.5,'grin')]:
        g.frame(t).save(args.out/(name+'-'+label+'.png'))
    assert np.array_equal(np.asarray(g.frame(0)),np.asarray(g.frame(DURATION))), 'Loop endpoints differ'
    if args.poster_only:return
    ffmpeg=encoder();path=args.out/(name+'.mp4')
    command=[ffmpeg,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','720x1080','-r',str(args.fps),'-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    p=subprocess.Popen(command,stdin=subprocess.PIPE)
    gif=[]
    try:
        for i in range(int(DURATION*args.fps)):
            im=g.frame(i/args.fps);p.stdin.write(im.tobytes())
            if i%2==0:gif.append(im.resize((300,450),Image.Resampling.LANCZOS))
            if i%args.fps==0:print(f'{name}: {i/args.fps:.0f}/{DURATION:.0f}s',flush=True)
    finally:p.stdin.close()
    if p.wait()!=0:raise RuntimeError('ffmpeg encoding failed')
    # A shared palette prevents the preview from flickering as frames change.
    palette=gif[len(gif)//2].quantize(colors=128)
    gif=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in gif]
    gif[0].save(args.out/(name+'.gif'),save_all=True,append_images=gif[1:],duration=round(2000/args.fps),loop=0,optimize=True)
    subprocess.run([ffmpeg,'-v','error','-i',str(path),'-f','null','-'],check=True)
    receipt={'name':name,'duration_seconds':DURATION,'fps':args.fps,'frames':int(DURATION*args.fps),'width':720,'height':1080,'codec':'h264','pixel_format':'yuv420p','audio':False,'loop_endpoints_equal':True,'decode_check':'passed','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'provenance':'Original deterministic geometry and procedural textures; no third-party media.'}
    (args.out/(name+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
