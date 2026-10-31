#!/usr/bin/env python3
"""Material/lighting realism pass on the original ghost animation.
Original procedural artwork; imports the v1 timeline/encoder without changing it.
"""
import importlib.util, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ghost_base',ROOT/'scripts/render-ghost-eyes.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
bezier,pulse,curve=base.bezier,base.pulse,base.curve

def field(rng,w,h,small,amount=1):
    data=rng.random((small,small)).astype(np.float32)
    return np.asarray(Image.fromarray(data).resize((w,h),Image.Resampling.BICUBIC))*amount

def rgb_image(a):return Image.fromarray(np.uint8(np.clip(a,0,255)))

class RealisticGhost(base.Ghost):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.materials={}
        for side in [-1,1]:
            rng=np.random.default_rng(5719+side*131)
            grain=field(rng,360,360,110)
            broad=field(rng,360,360,14)
            fine=field(rng,360,360,260)
            angular=rng.random(2048)
            for _ in range(2):angular=(np.roll(angular,1)+2*angular+np.roll(angular,-1))/4
            self.materials[side]=(grain,broad,fine,angular)
        self.eye_grid=np.meshgrid(np.arange(310,dtype=np.float32),np.arange(260,dtype=np.float32))
        self.scleras={side:self.sclera(side) for side in [-1,1]}
        self.upper_teeth=self.dentition(True)
        self.lower_teeth=self.dentition(False)

    def iris(self,pupil,phase,mirror=False):
        side=-1 if mirror else 1
        grain,broad,fine,angular=self.materials[side]
        x,y=self.x,self.y;r=np.sqrt(x*x+y*y);theta=np.arctan2(y,x)
        warp=theta+.047*(grain-.5)+.018*np.sin(13*theta+8*r)
        idx=((warp/math.tau*2048)%2048).astype(int)
        fibres=angular[idx]
        fibres2=angular[((idx+11*r+18*broad).astype(int))%2048]
        # Irregular collarette and crypts break up the computer-perfect sunburst.
        collarette=pupil+.17+.038*np.sin(19*theta)+.027*np.sin(31*theta+1.7)
        crypt=np.exp(-((r-collarette)/.055)**2)*np.clip((broad-.40)*2.1,0,1)
        inner=np.exp(-((r-pupil-.15)/.20)**2)
        stroma=.23+.62*fibres+.23*fibres2+.19*(grain-.5)+.10*(fine-.5)
        stroma*=.55+.45*inner
        stroma-=crypt*.32
        rings=.025*np.sin(111*r+5*broad)*(1-inner)
        stroma+=rings
        limbus=np.clip((1-r)*8.0,0,1)**1.3
        stroma*=limbus
        # Cool blue-green tissue, with tiny warmer flecks near the pupil.
        red=stroma*(48+28*broad)+inner*10*grain
        green=stroma*(122+30*broad)
        blue=stroma*(177+25*broad)
        rgb=np.stack([red,green,blue],axis=-1)*1.45
        edge=pupil+.006*np.sin(37*theta)+.004*np.sin(61*theta)
        mask=np.clip((r-edge)*150,0,1)
        rgb*=mask[:,:,None]
        rgb+=np.exp(-((r-edge-.018)/.017)**2)[:,:,None]*np.array([9,15,16])
        # Corneal reflections sit above the iris and remain on the same light side.
        highlight=np.exp(-(((x+.26)/.105)**2+((y+.32)/.070)**2)*2)
        soft=np.exp(-(((x+.19)/.21)**2+((y+.26)/.10)**2)*2)
        rgb+=highlight[:,:,None]*np.array([181,202,209])+soft[:,:,None]*np.array([13,20,24])
        rgb[r>1]=0
        return rgb_image(rgb)

    def sclera(self,side):
        xx,yy=self.eye_grid
        nx=(xx-155)/178;ny=(yy-133)/155
        nz=np.sqrt(np.clip(1-nx*nx-ny*ny,0,1))
        light=np.clip(-.23*nx-.32*ny+.84*nz,0,1)
        # A cool, low-key source with shadow toward the corners of the globe.
        rng=np.random.default_rng(115+side)
        grain=field(rng,310,260,95)
        diffuse=(.13+.87*light)*(.92+.08*grain)
        rgb=diffuse[:,:,None]*np.array([106,119,126])
        eye=rgb_image(rgb)
        vessels=Image.new('RGB',eye.size);vd=ImageDraw.Draw(vessels)
        for direction in [-1,1]:
            for j in range(8):
                start=np.array([155+direction*rng.uniform(130,154),rng.uniform(88,174)])
                end=np.array([155+direction*rng.uniform(48,87),rng.uniform(91,178)])
                c1=start+[-direction*25,rng.uniform(-24,24)]
                c2=end+[direction*24,rng.uniform(-26,26)]
                pts=bezier(start,c1,c2,end,45)
                curve(vd,pts,(20,9,12),1)
                branch=pts[24]
                target=branch+[-direction*23,rng.uniform(-22,22)]
                curve(vd,bezier(branch,branch+[-direction*9,2],target+[direction*4,8],target,20),(12,5,7),1)
        arr=np.asarray(eye).astype(np.float32)
        veins=np.asarray(vessels.filter(ImageFilter.GaussianBlur(.45)))
        # Red capillaries are subtle, not graphic lines on top of the eye.
        arr[:,:,0]+=veins[:,:,0]*.18;arr[:,:,1]-=veins[:,:,0]*.60;arr[:,:,2]-=veins[:,:,0]*.44
        return rgb_image(arr)

    def eye(self,t,side,opening,gaze,pupil,threat):
        w,h=310,260;cy=133
        eye=self.scleras[side].copy()
        iris=self.iris(pupil,t,side<0).resize((156,156),Image.Resampling.LANCZOS)
        iris_mask=Image.new('L',(156,156));ImageDraw.Draw(iris_mask).ellipse((0,0,155,155),fill=255)
        iris_mask=iris_mask.filter(ImageFilter.GaussianBlur(.7))
        ix=round(155-78+gaze[0]);iy=round(cy-78+gaze[1])
        eye.paste(iris,(ix,iy),iris_mask)
        tilt=-side*(2+15*threat)
        # Upper lids lead a blink; the lower lids move much less.
        upper=bezier((15,cy-tilt),(73,cy-93*opening-tilt),(228,cy-108*opening+tilt),(298,cy+tilt))
        lower=bezier((298,cy+tilt),(242,cy+72*opening+tilt),(78,cy+64*opening-tilt),(15,cy-tilt))
        mask=Image.new('L',(w,h));ImageDraw.Draw(mask).polygon([tuple(p) for p in np.vstack((upper,lower))],fill=255)
        # A real upper lid casts a soft shadow onto the eyeball.
        shade=Image.new('L',(w,h));sd=ImageDraw.Draw(shade)
        curve(sd,upper,180,28)
        shadow=np.asarray(shade.filter(ImageFilter.GaussianBlur(9)),dtype=np.float32)/255
        eye=rgb_image(np.asarray(eye)*(1-.88*shadow[:,:,None]))
        mask=mask.filter(ImageFilter.GaussianBlur(1.35))
        eye=ImageChops.multiply(eye,Image.merge('RGB',(mask,mask,mask)))
        # Restrained eyelid skin folds: a soft volume rather than a neon outline.
        skin=Image.new('RGB',(w,h));d=ImageDraw.Draw(skin)
        curve(d,upper,(16,24,30),10)
        curve(d,lower,(24,32,38),8)
        fold=upper.copy();fold[:,1]-=10+4*opening
        curve(d,fold,(9,14,18),4)
        skin=skin.filter(ImageFilter.GaussianBlur(3.6))
        eye=ImageChops.add(eye,skin)
        wet=Image.new('RGB',(w,h));wd=ImageDraw.Draw(wet)
        curve(wd,lower[16:54],(32,45,49),1)
        eye=ImageChops.add(eye,wet.filter(ImageFilter.GaussianBlur(.7)))
        # Small inner tear duct catches just a trace of muted violet light.
        ductx=291 if side<0 else 22
        duct=Image.new('RGB',(w,h));dd=ImageDraw.Draw(duct)
        ducty=cy+tilt if side<0 else cy-tilt
        dd.ellipse((ductx-4,ducty-2,ductx+4,ducty+3),fill=(23,16,23))
        eye=ImageChops.add(eye,duct.filter(ImageFilter.GaussianBlur(1)))
        return eye

    def dentition(self,upper):
        w,h=720,1080
        out=np.zeros((h,w,3),dtype=np.float32)
        rng=np.random.default_rng(848 if upper else 849)
        # Enamel is curved and translucent at the tips, with no luminous outline.
        for i in range(12):
            widths=[18,21,24,28,31,32,32,31,28,24,21,18]
            x=193+sum(widths[:i])+2*i;u=(x-360)/180
            y=(691-30*u*u) if upper else (738-37*u*u)
            width=widths[i]
            length=(37+3*math.cos(i*1.4)) if upper else (25+2*math.cos(i*1.7))
            if upper and i in (2,9):length+=7
            sign=1 if upper else -1
            def q(dx,dy):return (x+dx,y+sign*dy)
            pts=np.vstack((
                bezier(q(0,-10),q(7,-15),q(width-4,-14),q(width,-7),20),
                bezier(q(width,-7),q(width+1,12),q(width-3,length-2),q(width-9,length),20),
                bezier(q(width-9,length),q(7,length+3),q(1,length-1),q(0,8),20),
                bezier(q(0,8),q(-2,-3),q(-1,-7),q(0,-10),10)))
            tooth=Image.new('L',(w,h));ImageDraw.Draw(tooth).polygon([tuple(p) for p in pts],fill=255)
            left=max(0,int(x-5));right=int(x+width+5)
            top=max(0,int(np.min(pts[:,1])-4));bottom=min(h,int(np.max(pts[:,1])+5))
            yy,xx=np.mgrid[top:bottom,left:right]
            convex=np.clip(1-((xx-(x+width*.43))/(width*.68))**2,0,1)**.45
            lighting=(.30+.70*convex)*(.66+.34*np.clip(sign*(yy-y)/length,0,1))
            lighting*=.94+.06*rng.random(lighting.shape)
            rim=np.exp(-((yy-(y+sign*(length-2)))/3.5)**2)*.08
            color=(lighting+rim)[:,:,None]*np.array([144,153,153])
            color*=1-.35*abs(u)
            if not upper:color*=.72
            tm=np.asarray(tooth)[top:bottom,left:right]/255
            out[top:bottom,left:right]+=color*tm[:,:,None]
        return rgb_image(out)

    def mouth(self,t,grin):
        # The mouth remains present and articulates throughout all twelve seconds.
        # This is silent idle articulation, not speech/audio synchronization.
        jaw=18+12*math.sin(math.tau*t/3+.7)+4*math.sin(math.tau*t/1.2)
        lip=2.5*math.sin(math.tau*t/2+.25)
        corners=4*grin+1.5*math.sin(math.tau*t/4)
        x0,x1=180-10*grin,540+10*grin
        upper=bezier((x0,672-corners),(279,709+lip),(443,711+lip),(x1,667-corners))
        lower=bezier((x1,667-corners),(460,742+1.4*jaw),(259,746+1.4*jaw),(x0,672-corners))
        mask=Image.new('L',(720,1080));ImageDraw.Draw(mask).polygon([tuple(p) for p in np.vstack((upper,lower))],fill=255)
        mask=mask.filter(ImageFilter.GaussianBlur(.65))
        # Only the lower jaw moves; upper enamel stays anchored to the skull.
        shifted=Image.new('RGB',(720,1080));shifted.paste(self.lower_teeth,(0,round(jaw)))
        enamel=ImageChops.lighter(self.upper_teeth,shifted)
        out=ImageChops.multiply(enamel,Image.merge('RGB',(mask,mask,mask)))
        lips=Image.new('RGB',out.size);d=ImageDraw.Draw(lips)
        curve(d,upper,(22,24,29),8);curve(d,lower,(28,34,37),10)
        out=ImageChops.add(out,lips.filter(ImageFilter.GaussianBlur(3)))
        wet=Image.new('RGB',out.size);d=ImageDraw.Draw(wet)
        curve(d,lower[21:51],(24,29,31),1)
        return ImageChops.add(out,wet.filter(ImageFilter.GaussianBlur(.7)))

    def frame(self,t):
        t=t%base.DURATION
        threat=pulse(3.,5.3,8.3,10.7,t)
        grin=pulse(4.1,6.,8.,10.5,t)
        blink=pulse(2.39,2.49,2.53,2.75,t)
        gaze_x=-13*pulse(.80,.94,1.85,2.04,t)+17*pulse(8.6,8.76,9.65,9.88,t)
        gaze_y=-3*pulse(.8,.94,1.85,2.04,t)
        opening=(.94-.24*threat)*(1-.97*blink)
        pupil=.37-.055*threat+.009*math.sin(math.tau*t/base.DURATION)
        layer=Image.new('RGB',(720,1080))
        # Hold the head still; gaze shifts settle instead of perpetually floating.
        for side in [-1,1]:
            eye=self.eye(t,side,opening*(.98 if side>0 else 1),(gaze_x,gaze_y),pupil,threat)
            layer.paste(eye,(48 if side<0 else 362,342+(2 if side>0 else 0)))
        if not self.eyes_only:layer=ImageChops.add(layer,self.mouth(t,grin))
        # Much less bloom: highlights stay localized, pupils and shadows stay deep.
        glow=layer.resize((180,270)).filter(ImageFilter.GaussianBlur(3)).resize(layer.size)
        glow=glow.point(lambda v:round(v*.13))
        layer=ImageChops.add(layer,glow)
        if (self.width,self.height)!=(720,1080):layer=layer.resize((self.width,self.height),Image.Resampling.LANCZOS)
        return layer

if __name__=='__main__':
    base.Ghost=RealisticGhost
    if '--out' not in sys.argv and not any(a.startswith('--out=') for a in sys.argv):
        sys.argv.extend(['--out',str(ROOT/'content/animations/ghost-eyes-realistic')])
    base.main()
