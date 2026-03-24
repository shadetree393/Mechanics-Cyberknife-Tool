#!/usr/bin/env python3
# MECHANIC'S CYBERKNIFE v3.4 - Diagnostic Platform
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import random, time, math, csv
from collections import deque

try:
    import matplotlib; matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL = True
except: MPL = False

BG="#0d1117";PANEL="#161b22";DARK="#0a0e14";GREEN="#00ff88";AMBER="#ffaa00"
RED="#ff4040";BLUE="#4488ff";CYAN="#00ccff";YELL="#ffff44";PURP="#cc55ff"
WHITE="#ddeeff";GRAY="#445566";DIM="#223344";ORANGE="#ff7722";TEAL="#00ddaa"
FS=8;FM=9
FONT=("Courier New",FM,"bold");FONT_S=("Courier New",FS)
RPM_BINS=[500,1000,1500,2000,2500,3000,3500,4000,4500,5000,5500,6000]
MAP_BINS=[20,30,40,50,60,70,80,90,100]

def randn():
    u,v=0,0
    while not u: u=random.random()
    while not v: v=random.random()
    return math.sqrt(-2*math.log(u))*math.cos(2*math.pi*v)

def interp1d(xs,ys,v):
    if v<=xs[0]: return ys[0]
    if v>=xs[-1]: return ys[-1]
    for i in range(len(xs)-1):
        if xs[i]<=v<=xs[i+1]:
            t=(v-xs[i])/(xs[i+1]-xs[i]); return ys[i]+t*(ys[i+1]-ys[i])
    return ys[-1]

def idx_bin(bins,v):
    for i,b in enumerate(bins):
        if v<=b: return i
    return len(bins)-1

def interp2d(tbl,rpm,kpa):
    ri=idx_bin(RPM_BINS,rpm); mi=idx_bin(MAP_BINS,kpa)
    r0,r1=max(0,ri-1),min(len(RPM_BINS)-1,ri); m0,m1=max(0,mi-1),min(len(MAP_BINS)-1,mi)
    rx=max(0,min(1,(rpm-RPM_BINS[r0])/max(RPM_BINS[r1]-RPM_BINS[r0],1)))
    mx=max(0,min(1,(kpa-MAP_BINS[m0])/max(MAP_BINS[m1]-MAP_BINS[m0],1)))
    return(tbl[m0][r0]*(1-rx)*(1-mx)+tbl[m0][r1]*rx*(1-mx)+tbl[m1][r0]*(1-rx)*mx+tbl[m1][r1]*rx*mx)

ENGINE_PROFILES={
  "i4_na":      dict(name="I4 NA 2.0L",       cyl=4,disp=2.0,cr=10.2,idle=800, maxr=7200,tqr=4000,maxb=0, inj="PFI", diesel=False,turbo=False,glow=False,oi=25,oc=50,egt=650,pat="60-2",fir=[1,3,4,2]),
  "v6_na":      dict(name="V6 NA 3.5L",        cyl=6,disp=3.5,cr=10.8,idle=700, maxr=6800,tqr=3800,maxb=0, inj="PFI", diesel=False,turbo=False,glow=False,oi=28,oc=55,egt=660,pat="60-2",fir=[1,2,3,4,5,6]),
  "v8_na":      dict(name="V8 NA 5.7L",        cyl=8,disp=5.7,cr=9.5, idle=650, maxr=6500,tqr=3200,maxb=0, inj="SFI", diesel=False,turbo=False,glow=False,oi=25,oc=45,egt=680,pat="58x", fir=[1,8,4,3,6,5,7,2]),
  "i4_turbo":   dict(name="I4 Turbo 2.0T",     cyl=4,disp=2.0,cr=9.0, idle=800, maxr=6800,tqr=1800,maxb=18,inj="DI",  diesel=False,turbo=True, glow=False,oi=30,oc=60,egt=720,pat="60-2",fir=[1,3,4,2]),
  "v6_turbo":   dict(name="V6 BiTurbo 3.0T",   cyl=6,disp=3.0,cr=9.3, idle=700, maxr=6500,tqr=1600,maxb=16,inj="DI",  diesel=False,turbo=True, glow=False,oi=35,oc=65,egt=750,pat="60-2",fir=[1,4,2,5,3,6]),
  "v8_turbo":   dict(name="V8 SC 6.2L",        cyl=8,disp=6.2,cr=9.1, idle=650, maxr=6200,tqr=2000,maxb=9, inj="SFI", diesel=False,turbo=True, glow=False,oi=30,oc=55,egt=760,pat="58x", fir=[1,8,4,3,6,5,7,2]),
  "i4_diesel":  dict(name="I4 Diesel 2.2L",    cyl=4,disp=2.2,cr=16.5,idle=850, maxr=4800,tqr=2000,maxb=22,inj="CRDI",diesel=True, turbo=True, glow=True, oi=35,oc=65,egt=580,pat="36-1",fir=[1,3,4,2]),
  "v6_diesel":  dict(name="V6 TDI 3.0L",       cyl=6,disp=3.0,cr=16.8,idle=800, maxr=4500,tqr=1750,maxb=24,inj="CRDI",diesel=True, turbo=True, glow=True, oi=40,oc=70,egt=590,pat="36-1",fir=[1,4,2,5,3,6]),
  "i6_hd":      dict(name="I6 HD Diesel 6.7L", cyl=6,disp=6.7,cr=17.3,idle=700, maxr=3400,tqr=1500,maxb=35,inj="CRDI",diesel=True, turbo=True, glow=True, oi=45,oc=80,egt=540,pat="36-1",fir=[1,5,3,6,2,4]),
  "v8_hd":      dict(name="V8 HD Diesel 6.6L", cyl=8,disp=6.6,cr=17.5,idle=750, maxr=3200,tqr=1600,maxb=30,inj="CRDI",diesel=True, turbo=True, glow=True, oi=45,oc=80,egt=545,pat="58x", fir=[1,8,4,3,6,5,7,2]),
  "i6_semi":    dict(name="I6 Semi 15L",        cyl=6,disp=15., cr=18.0,idle=600, maxr=2100,tqr=1100,maxb=45,inj="CRDI",diesel=True, turbo=True, glow=False,oi=50,oc=90,egt=510,pat="36-1",fir=[1,5,3,6,2,4]),
  "i6_cat":     dict(name="I6 Cat 13L",         cyl=6,disp=13., cr=17.5,idle=600, maxr=2100,tqr=1000,maxb=42,inj="CRDI",diesel=True, turbo=True, glow=False,oi=50,oc=88,egt=515,pat="36-1",fir=[1,5,3,6,2,4]),
}
TRANS_PROFILES={
  "6spd":   dict(name="6L80 Auto",    gears=6,ratios=[4.03,2.36,1.53,1.15,0.85,0.67],final=3.42,tcc=True, li=70,ld=140),
  "8spd":   dict(name="8HP Auto",     gears=8,ratios=[4.71,3.14,2.11,1.67,1.29,1.0,0.84,0.67],final=3.15,tcc=True,li=75,ld=145),
  "cvt":    dict(name="CVT Belt",     gears=0,ratios=[2.5,1.0,0.45],final=4.1,tcc=False,li=50,ld=200),
  "dct":    dict(name="DCT 7-spd",    gears=7,ratios=[3.9,2.7,1.93,1.45,1.17,0.95,0.81],final=3.06,tcc=False,li=80,ld=160),
  "allison":dict(name="Allison 1000", gears=6,ratios=[3.51,1.9,1.42,1.0,0.75,0.64],final=3.73,tcc=True,li=90,ld=175),
  "prius":  dict(name="Toyota EVT",   gears=0,ratios=[2.4,1.0,0.4],final=3.267,tcc=False,li=0,ld=0),
}
FUEL_STOICH={"E10":14.5,"E85":9.8,"91oct":14.7,"93oct":14.7,"98oct":14.7,"diesel":14.5,"B20":14.1}

class ECUMaps:
    def __init__(self): self.reset()
    def reset(self):
        self.ve   =[[max(20,min(108,round(38+62*(mi/8)*(0.55+0.45*math.exp(-0.5*((ri-6)/3.2)**2))+randn(),1))) for ri in range(12)] for mi in range(9)]
        self.ign  =[[max(0,min(45,round(8+ri*1.9*(1-(mi/8)*0.5)+randn()*0.3,1))) for ri in range(12)] for mi in range(9)]
        self.afr  =[[round(12.5+(ri/11)*0.8,2) if mi/8>0.85 else round(15.2+(ri/11)*0.4,2) if mi/8<0.25 else round(14.7+randn()*0.1,2) for ri in range(12)] for mi in range(9)]
        self.boost=[[0.0]*12 for _ in range(9)]
        self.req_fuel=7.2; self.soft_cut=6800; self.hard_cut=7200
        self.accel_mult=1.6; self.knock_step=2.5; self.knock_max=12.0; self.knock_rec=0.3; self.fuel_psi=43.5
        self.clt_ax=[-40,-20,0,20,40,60,80,90,100]; self.clt_corr=[185,162,142,122,111,105,100,100,98]
        self.iat_ax=[-40,-20,0,20,40,60,80,100];    self.iat_corr=[114,109,105,100,96,91,85,78]
        self.dt_v=[8,9,10,11,12,13,14,15];           self.dt_ms=[1.9,1.6,1.35,1.1,0.9,0.8,0.7,0.65]
        self.idle_ax=[0,20,40,60,80,90];             self.idle_rpm=[1500,1300,1050,900,850,800]
    def rebuild_boost(self,p):
        mb=p["maxb"]
        self.boost=[[max(0,min(mb,round(mb*(0.2+ri/11*0.8)*(0.3+mi/8*0.7)+randn()*0.3,1))) for ri in range(12)] for mi in range(9)]

class EnginePhysics:
    def __init__(self,maps):
        self.maps=maps; self.profile=ENGINE_PROFILES["i4_na"]; self.trans=TRANS_PROFILES["6spd"]
        self.env=dict(altitude=0,ambient_temp=20,fuel_type="E10",boost_enabled=True,boost_target=14,cond_override="auto",road_grade=0)
        self._reset()
    def _reset(self):
        p=self.profile
        self.rpm=float(p["idle"]); self.map_kpa=35.0; self.tps=0.0
        self.clt=20.0; self.iat=20.0; self.batt=12.6; self.gear=1; self.spd=0.0
        self.afr=14.7; self.lam=1.0; self.pw=3.0; self.dc=0.0; self.dwell=3.5; self.adv=10.0
        self.egt=600.0; self.oil=45.0; self.stft=0.0; self.ltft=0.0
        self.ego=False; self.kret=0.0; self.klvl=0.0; self.kcnt=0
        self.at=0.0; self.ptps=0.0; self.ptt=time.time(); self.rtgt=float(p["idle"])
        self.st=0.0; self.scenario="warmup"
        self.active_dtcs=[]; self.stored_dtcs=[]
        self.fault_o2=False; self.fault_map=False; self.fault_clt=False
        self.fault_miss=0; self.fault_lean=False; self.fault_ign=False; self.fault_inj=False
        self.cyl_kill=[False]*8
        self.ve_live=0.0; self.ign_live=0.0; self.afr_tgt=14.7
        self.accel=False; self.boost_psi=0.0; self.glow_ready=False
        self.hv_soc=68.0; self.hv_voltage=201.6; self.hv_current=0.0
        self.mg1_rpm=0.0; self.mg2_rpm=0.0; self.connected=False
    def set_profile(self,key):
        self.profile=ENGINE_PROFILES.get(key,ENGINE_PROFILES["i4_na"]); self.maps.rebuild_boost(self.profile)
    def set_trans(self,key):
        self.trans=TRANS_PROFILES.get(key,TRANS_PROFILES["6spd"])
    def step(self,dt):
        p=self.profile; t=self.trans; m=self.maps; self.st+=dt
        if self.env["cond_override"]!="auto": self._apply_cond(self.env["cond_override"],dt)
        else: self._auto_scenario(dt)
        if self.tps<1: self.rtgt=interp1d(m.idle_ax,m.idle_rpm,self.clt)+randn()*15
        rpm_max=p["maxr"]*(0.85 if p["diesel"] else 1.0)
        self.rpm+=(self.rtgt-self.rpm)*3*dt+randn()*self.rpm*0.003
        self.rpm=max(0,min(rpm_max,self.rpm))
        baro=max(0.6,1-(self.env["altitude"]/10000)*0.12)
        mt=max(15,min(105,20+self.tps*0.78-(self.rpm/rpm_max)*8))
        if self.fault_map: mt=50
        if self.fault_lean: mt+=8
        mt*=baro; self.map_kpa+=(mt-self.map_kpa)*5*dt; self.map_kpa=max(15,min(105,self.map_kpa))
        if p["turbo"] and self.env["boost_enabled"]:
            tgt=min(p["maxb"],self.env["boost_target"])*(self.tps/100)
            if self.rpm<p["maxr"]*0.3: tgt*=self.rpm/max(p["maxr"]*0.3,1)
            self.boost_psi+=(tgt-self.boost_psi)*2*dt; self.boost_psi=max(0,self.boost_psi)
            self.map_kpa=min(105,self.map_kpa+self.boost_psi*6.895*0.1)
        else: self.boost_psi=0.0
        self.ve_live=interp2d(m.ve,self.rpm,self.map_kpa)
        stoich=FUEL_STOICH.get(self.env["fuel_type"],14.7)
        self.afr_tgt=interp2d(m.afr,self.rpm,self.map_kpa)*(stoich/14.7)
        self.ign_live=interp2d(m.ign,self.rpm,self.map_kpa)
        clt_use=-40 if self.fault_clt else self.clt
        cc=interp1d(m.clt_ax,m.clt_corr,clt_use)/100
        ic=interp1d(m.iat_ax,m.iat_corr,self.iat)/100
        dead=interp1d(m.dt_v,m.dt_ms,self.batt)
        now=time.time(); rate=(self.tps-self.ptps)/max(now-self.ptt,0.001)*0.1
        self.ptps=self.tps; self.ptt=now
        if rate>m.accel_mult: self.at=0.35
        self.accel=self.at>0; am=1+(self.at>0)*(m.accel_mult-1)*(self.at/0.35)
        if self.at>0: self.at=max(0,self.at-dt)
        killed=sum(1 for k in self.cyl_kill[:p["cyl"]] if k)
        active_cyls=max(1,p["cyl"]-killed); cf=p["cyl"]/active_cyls
        if self.fault_inj: self.pw=99; self.dc=100
        else:
            et=1+(self.stft+self.ltft)/100
            self.pw=m.req_fuel*(self.ve_live/100)*(stoich/self.afr_tgt)*cc*ic*am*et*cf+dead
            if self.rpm>=m.hard_cut: self.pw=0
            elif self.rpm>=m.soft_cut and random.random()<0.5: self.pw=0
            cy=120000/max(self.rpm,100); self.dc=min(100,(self.pw/cy)*100)
        ib=self.ign_live
        if self.fault_ign: ib=max(0,ib-10)
        risk=max(0,(ib-25)/15)*(self.map_kpa/100)*(self.rpm/rpm_max)
        mr=0.4 if (self.fault_miss>0 and random.random()<0.15) else 0
        if random.random()<(risk+mr)*0.08:
            self.kret=min(self.kret+m.knock_step,m.knock_max); self.klvl=min(1,self.klvl+0.4); self.kcnt+=1
        else: self.kret=max(0,self.kret-m.knock_rec*dt*10); self.klvl=max(0,self.klvl-0.05)
        self.adv=max(0,ib-self.kret); self.dwell=max(1.5,3.8*(13.5/max(self.batt,8))-self.rpm*0.0001)
        lean=1.5 if self.fault_lean else 0
        if self.fault_o2: self.afr=self.afr_tgt+lean+randn()*0.3; self.ego=False
        elif self.fault_inj: self.afr=10.2+random.random()*1.3; self.ego=False
        else: self.afr=max(8,min(22,self.afr_tgt+lean+randn()*0.08))
        self.lam=self.afr/stoich
        if not self.fault_o2 and self.clt>75 and self.tps<80 and self.rpm<4500:
            self.ego=True; self.stft+=(self.afr_tgt-self.afr)*0.8*dt
            self.stft=max(-25,min(25,self.stft)); self.ltft+=self.stft*0.003*dt; self.ltft=max(-25,min(25,self.ltft))
        elif not self.fault_o2: self.stft*=0.95; self.ego=False
        self.egt=max(200,min(1050,p["egt"]+(self.rpm/rpm_max)*280+(self.map_kpa/100)*180+(self.lam-1)*100+randn()*5))
        if self.fault_clt: self.clt=-40+randn()*0.5
        elif self.clt<90: self.clt+=((self.rpm/rpm_max)*0.35+(self.map_kpa/100)*0.18)*dt
        else: self.clt=87+randn()
        self.iat+=(self.env["ambient_temp"]+self.rpm*0.003-self.iat)*0.01*dt+randn()*0.1
        tv=14.2 if self.rpm>900 else 12.0; self.batt=max(10,min(15,self.batt+(tv-self.batt)*dt+randn()*0.02))
        if t["gears"]>0:
            r=t["ratios"][max(0,min(t["gears"]-1,self.gear-1))]
        else: r=t["ratios"][1]
        self.spd=max(0,self.rpm/(r*t["final"])*p["disp"]/2*60/1000*0.8)
        self.oil=max(0,min(p["oc"]+15,0 if self.rpm<100 else p["oi"]+(self.rpm/rpm_max)*(p["oc"]-p["oi"])+randn()))
        self.glow_ready=p["glow"] and self.clt<40
        if t.get("name","")=="Toyota EVT":
            self.hv_soc=max(20,min(80,self.hv_soc+(random.random()-0.5)*0.2))
            self.hv_voltage=201.6*(self.hv_soc/80)*0.9+randn(); self.hv_current=(self.tps/100)*50+randn()*2
            self.mg1_rpm=self.rpm*0.4+randn()*10; self.mg2_rpm=self.spd*45+randn()*5
        self._update_dtcs()
    def _auto_scenario(self,dt):
        p=self.profile; c=self.st%150
        if   c<20:  self.scenario="warmup"; self.tps=max(0,0.5+randn()*0.3); self.gear=1
        elif c<40:  self.scenario="cruise"; self.tps=max(0,22+math.sin(self.st*0.1)*5); self.gear=3; self.rtgt=2200+math.sin(self.st*0.08)*200
        elif c<60:  self.scenario="wot";    self.tps=min(100,98+randn()*0.5); self.gear=2; self.rtgt=min(p["maxr"]*0.9,self.rtgt+40)
        elif c<80:  self.scenario="decel";  self.tps=0; self.gear=4; self.rtgt=max(p["idle"],self.rtgt-70)
        elif c<100: self.scenario="hwy";    self.tps=max(0,35+randn()*2); self.gear=4; self.rtgt=1800 if p["diesel"] else 3000+randn()*100
        else:       self.scenario="idle";   self.tps=max(0,0.2+randn()*0.2); self.gear=1; self.rtgt=p["idle"]
        if self.env["road_grade"]>0: self.rtgt+=self.env["road_grade"]*30
    def _apply_cond(self,cond,dt):
        p=self.profile
        c={"warmup":(0.5,1,p["idle"]*1.3),"idle":(0.2,1,p["idle"]),"cruise":(25,4,2200),
           "wot":(100,2,min(p["maxr"]*0.9,self.rtgt+30)),"decel":(0,4,max(p["idle"],self.rtgt-50)),
           "boost_test":(85,2,min(p["maxr"]*0.85,self.rtgt+20)),"regen":(0,5,max(p["idle"],self.rtgt-40))}
        if cond in c:
            tp,g,rt=c[cond]; self.tps=float(tp); self.gear=g; self.rtgt=float(rt); self.scenario=cond
        else: self._auto_scenario(dt)
    def _update_dtcs(self):
        checks=[(self.batt<11,"P0562","Battery Voltage Low"),(self.oil<8 and self.rpm>500,"P0520","Oil Pressure Low"),
                (self.ltft>20,"P0171","Fuel Trim Lean B1"),(self.ltft<-20,"P0172","Fuel Trim Rich B1"),
                (self.kcnt>50,"P0325","Knock Sensor Circuit"),(self.fault_o2,"P0131","O2 Sensor Low B1S1"),
                (self.fault_miss>0,"P030"+str(self.fault_miss),"Cyl "+str(self.fault_miss)+" Misfire"),
                (self.fault_clt,"P0117","ECT Sensor Low"),(self.fault_inj,"P0201","Injector Circuit Cyl1")]
        codes=[d[0] for d in self.active_dtcs]
        for cond,code,desc in checks:
            if cond and code not in codes:
                self.active_dtcs.append((code,desc))
                if not any(d[0]==code for d in self.stored_dtcs): self.stored_dtcs.append((code,desc))
    def clear_dtcs(self):
        self.active_dtcs.clear(); self.stft=0; self.ltft=0; self.kcnt=0

class ScopeGen:
    SIGS={"Wideband O2":{"col":"#00ff88"},"Narrowband O2":{"col":"#ff8844"},"MAP Sensor":{"col":"#4488ff"},
          "TPS":{"col":"#ffff44"},"CLT":{"col":"#ff4040"},"IAT":{"col":"#00ccff"},"Battery":{"col":"#cc55ff"},
          "Injector PW":{"col":"#ffaa00"},"Crank Signal":{"col":"#00ff88"},"Cam Signal":{"col":"#aaffcc"},
          "Ignition Pri":{"col":"#ff6644"},"Knock Sensor":{"col":"#ff4488"},"EGT":{"col":"#ff9900"},
          "Oil Pressure":{"col":"#33ddaa"},"Boost Pressure":{"col":"#dd88ff"}}
    def __init__(self,eng,npts=200):
        self.eng=eng; self.npts=npts; self.t=0.0
        self.bufs={k:deque(maxlen=npts) for k in self.SIGS}
    def step(self,dt):
        self.t+=dt; e=self.eng; f=e.rpm/60
        v={
            "Wideband O2":   e.afr+math.sin(self.t*0.3)*0.4+randn()*0.06,
            "Narrowband O2": 0.15+random.random()*0.15 if e.lam<1 else 0.8+random.random()*0.15,
            "MAP Sensor":    e.map_kpa+math.sin(self.t*f*math.pi*2)*3+randn()*0.5,
            "TPS":           e.tps+randn()*0.2,
            "CLT":           e.clt+randn()*0.1,
            "IAT":           e.iat+randn()*0.1,
            "Battery":       e.batt+math.sin(self.t*1.2)*0.08+randn()*0.01,
            "Injector PW":   e.pw+randn()*0.03,
            "Crank Signal":  3.3 if (int(self.t*f*60)%60<58 and math.sin(self.t*f*2*math.pi*30)>0.2) else 0.1,
            "Cam Signal":    5.0 if math.sin(self.t*(f/2)*2*math.pi)>0.4 else 0.0,
            "Ignition Pri":  12.0 if (self.t*f/2*2*math.pi%(2*math.pi))<(e.dwell/1000*max(f/2,0.01)*2*math.pi) else 0.0,
            "Knock Sensor":  e.klvl*math.sin(self.t*800+randn())*2.5+randn()*0.08,
            "EGT":           e.egt+randn()*4,
            "Oil Pressure":  e.oil+randn()*1.5,
            "Boost Pressure":e.boost_psi+randn()*0.3,
        }
        for k,val in v.items(): self.bufs[k].append(val)

class CANBusSim:
    J1939={"F004":("EEC1","Engine Speed"),"FEFF":("EEC2","Throttle"),"FEF5":("CCVS","Veh Speed"),
           "FEEE":("ET1","Eng Temps"),"FEEF":("EFL","Fluid/Press"),"FEF6":("LFC","Fuel Rate")}
    def __init__(self,eng):
        self.eng=eng; self.j1939=deque(maxlen=100); self.obd=deque(maxlen=100)
        self.lin=deque(maxlen=30); self.proto=deque(maxlen=200)
        self.capturing=False; self.autopoll=False; self._jt=0.0; self._ot=0.0; self._lt=0.0
        self.community=[{"id":"0x7E8","name":"RPM OBD","source":"SAE J1979"},
                        {"id":"0x3B0","name":"Coolant GMLAN","source":"GM spec"},
                        {"id":"0x540","name":"VVT Position","source":"ToyotaNation"},
                        {"id":"0x641","name":"Boost Ford MS-CAN","source":"FordTech"}]
    def step(self,dt):
        self._jt+=dt; self._ot+=dt; self._lt+=dt; e=self.eng
        if self._jt>0.2:
            self._jt=0; pgn=random.choice(list(self.J1939.keys())); nm,desc=self.J1939[pgn]
            data=" ".join("%02X"%random.randint(0,255) for _ in range(8))
            self.j1939.append({"t":"%.2f"%(time.time()%10000),"id":"0CF"+pgn+"00","pgn":pgn,"name":nm,"data":data,"decoded":desc+" "+str(int(e.rpm))})
        if self._ot>0.4 and self.autopoll:
            self._ot=0; pid=random.choice(["0C","0D","05","0F","04","11"])
            self.obd.append({"t":"%.2f"%(time.time()%10000),"id":"0x7DF","dir":"Req","data":"02 01 "+pid+" 00 00 00 00 00","decoded":""})
            self.obd.append({"t":"%.2f"%(time.time()%10000),"id":"0x7E8","dir":"Resp","data":"04 41 "+pid+" %02X 00 00"%random.randint(0,255),"decoded":"PID "+pid})
        if self._lt>0.3:
            self._lt=0
            nodes={"0x01":"HVAC","0x02":"Mirror","0x10":"Window","0x20":"Seat","0x3C":"Lighting"}
            lid=random.choice(list(nodes.keys()))
            self.lin.append({"id":lid,"node":nodes[lid],"data":" ".join("%02X"%random.randint(0,255) for _ in range(4)),"chk":"%02X"%random.randint(0,255)})
        if self.capturing:
            lid="0x%03X"%random.randint(0,0x7FF); data=["%02X"%random.randint(0,255) for _ in range(8)]
            match=next((c["name"] for c in self.community if c["id"].lower()==lid.lower()),"")
            self.proto.append({"id":lid,"data":data,"match":match})

class CyberKnife(tk.Tk):
    SVC={
      "generic":[("Oil Reset","0x31 0xA100","Resets oil life 100% — key cycle after"),
                 ("Throttle Relearn","Disconnect bat 10min idle 10min","IAC/DBW adaptation"),
                 ("EVAP Test","Mode01 PID 41 EVAP monitor","Leak readiness — cold soak needed"),
                 ("DPF Regen","0x31 0xBF00",">60kph sustained EGT 550-650C"),
                 ("AdBlue Reset","0x2E 0xD003","Reset DEF timer after fill"),
                 ("Steering Cal","0x31 0xF0A1","Level ground, steering centered"),
                 ("EPB Service","0x31 0x0206","Retract calipers for pad swap"),
                 ("Idle Relearn","Warm idle 10min, drive 30min","Relearns fueling LTFT windows")],
      "bmw":[("CBS Reset","Kombi 0x31 service category","BMW Condition Based Service"),
             ("Trans Svc","ZGM 0x31 0x6020 01 00","Change at 80k, not lifetime"),
             ("Injector Coding","DME 0x2E 0x12AB 8-byte","8-digit flow code on injector"),
             ("DME Adapt Clear","0x31 0xFF01 01","Clear fuel/idle/misfire adapts"),
             ("VANOS Adapt","0x31 0x9000","Cam phaser relearn after timing work"),
             ("Battery Reg","BMS 0x2E 0xC840","Register Ah and chemistry into BMS"),
             ("EGS Adapt","EGS 0x31 0xE100","Shift adapts — new fluid or component")],
      "ford":[("KAM Reset","PCM 0x11 01","Clear KAM — 40min idle relearn"),
              ("PATS Key","PCM 0x27 + 0x2E","Needs 2 existing keys or override"),
              ("MS-CAN Actuator","BCM 0x31 at 125kbps","Ford body separate 125kbps bus"),
              ("Injector Char","0x2E 0xF00A 4B/cyl","Flow offset codes per cylinder"),
              ("ETC Throttle","0x31 0xF080 01","Idle hot no loads 10 min"),
              ("DPS6 Clutch","TCM 0x31 0x0600","PowerShift kiss-point 10 slow engagements")],
      "gm":[("KAM Reset","0x27 seed+key 0x11 03","Clear idle/fuel/trans adapts"),
            ("CASE Relearn","Fixed idle, throttle cycles","CKP pattern removal after crank/sensor"),
            ("AFM Check","PCM 0x22 0xB003","Active Fuel Management P3400/P3401"),
            ("Allison Reset","TCM 0x2E 0x4501","TranSynd interval — 250kbps J1939"),
            ("TPMS Relearn","Drive>25kph 10min or tool","Schrader 315MHz FL-FR-RL-RR"),
            ("Inj Balance","PCM 0x31 0xA105 01","Per-cyl fuel trim all cyls needed")],
      "toyota":[("Throttle Relearn","IGN ON-OFF-5sec idle 10min","Sub-throttle valve relearn"),
                ("VSC Cal","Chassis 0x31 0x0234","Yaw/lateral G — level stationary"),
                ("D4-S Injector","ECM 0x2E 0x01A5 12 bytes","GR engine injector flow codes"),
                ("HV Inspect","HV ECU 0x22 0x0281","Cell voltages spread >0.3V = failing"),
                ("EPB Bleed","Skid ECU 0x31 0x0100","ABS open — 2 operators needed"),
                ("Speedo Cal","Combo meter 0x2E ratio","Required after tire size change")],
      "vw":[("TDI DPF Reset","ECM 0x31 routine 0x03","After new DPF reset ash counter"),
            ("Injector IQ","ECM 0x2E 0x0100 8 codes","IQ codes on injector body"),
            ("DSG Reset","Mechatronic 0x2E counter","After fluid+filter change"),
            ("Throttle Adapt","Basic settings group 060","Lower stop then upper stop learn"),
            ("AdBlue Quality","ECM 0x31 0x4401","NOx sensor baseline after exhaust work"),
            ("Air Mass Adapt","Basic settings 0x0023","MAF adaptation after replacement")],
      "hd":[("Cummins Clear","J1939 DM11 PGN 0xFEDA","HD DTC clear tester addr 0xF9"),
            ("DDEC Reset","SPN 2848 FMI 14","Detroit Diesel J1939 proprietary SPNs"),
            ("Allison Cal","Allison DOC 250kbps 29-bit","Shift cals — needs DOC or J1939"),
            ("Regen Force","J1939 0x31 DPF >95% soot","Neutral PTO-off park-brake 1200rpm"),
            ("EGR Cal","J1939 DM7 PGN 0xC300","EGR valve cal after cleaning/replace"),
            ("Inj Trim HD","EEPROM via J2534","INSITE/DDDL — individual cyl trim")],
    }
    FAULTS=[("fault_o2","O2 Sensor Fail","Stuck low — open loop no EGO"),
            ("fault_map","MAP Sensor Fail","Stuck 50kPa — stale fueling"),
            ("fault_clt","CLT Sensor Open","Reads -40C — cold start locked"),
            ("fault_lean","Vacuum Leak","Unmetered air — lean AFR hunt"),
            ("fault_ign","Retarded Timing","10 deg pulled — power loss detonate risk"),
            ("fault_inj","Stuck Open Injector","Shorted driver — flood/hydrolocking risk")]
    MOD_FAULTS=[("abs","C0040","ABS Wheel Speed FL open/tone ring"),
                ("abs","C0060","ABS Pump Motor overcurrent"),
                ("srs","B0020","Driver Airbag Squib open — clock spring"),
                ("tcu","P0750","Shift Sol-A fault — open/shorted harness"),
                ("bcm","B2103","PATS Transponder no signal — reader/key"),
                ("tpms","C1731","TPMS Sensor FL no signal — battery/RF"),
                ("hv","P0AFA","HV Battery cell undervoltage — ageing")]

    def __init__(self):
        super().__init__()
        self.title("MECHANIC'S CYBERKNIFE v3.4")
        self.configure(bg=BG); self.resizable(True,True)
        self.maps=ECUMaps(); self.engine=EnginePhysics(self.maps)
        self.scope=ScopeGen(self.engine); self.can=CANBusSim(self.engine)
        self.logging=False; self.log_data=[]; self._probe_cb=None; self._active_tab="mech"
        self._build_header()
        self._build_status_bar()
        self._build_dtc_bar()
        self._build_tabs()
        self._build_all_tabs()
        self._tick()

    def _build_header(self):
        bar=tk.Frame(self,bg="#0a1020",pady=2); bar.pack(fill=tk.X)
        tk.Label(bar,text="ENGINE:",bg="#0a1020",fg=GRAY,font=FONT_S).pack(side=tk.LEFT,padx=3)
        self.eng_var=tk.StringVar(value="I4 NA 2.0L")
        names=[v["name"] for v in ENGINE_PROFILES.values()]
        cb=ttk.Combobox(bar,textvariable=self.eng_var,values=names,width=20,font=FONT_S,state="readonly")
        cb.pack(side=tk.LEFT,padx=2); cb.bind("<<ComboboxSelected>>",self._on_eng)
        tk.Label(bar,text="TRANS:",bg="#0a1020",fg=GRAY,font=FONT_S).pack(side=tk.LEFT,padx=3)
        self.trans_var=tk.StringVar(value="6spd")
        ttk.Combobox(bar,textvariable=self.trans_var,values=list(TRANS_PROFILES.keys()),width=10,font=FONT_S,state="readonly").pack(side=tk.LEFT,padx=2)
        self.trans_var.trace_add("write",lambda *a:self.engine.set_trans(self.trans_var.get()))
        tk.Label(bar,text="COND:",bg="#0a1020",fg=GRAY,font=FONT_S).pack(side=tk.LEFT,padx=3)
        self.cond_var=tk.StringVar(value="auto")
        ttk.Combobox(bar,textvariable=self.cond_var,values=["auto","warmup","idle","cruise","wot","decel","boost_test","regen"],width=11,font=FONT_S,state="readonly").pack(side=tk.LEFT,padx=2)
        self.cond_var.trace_add("write",lambda *a:self.engine.env.update({"cond_override":self.cond_var.get()}))
        self.eng_badge=tk.Label(bar,text="I4 NA 2.0L",bg="#001830",fg=BLUE,font=FONT_S); self.eng_badge.pack(side=tk.LEFT,padx=4)
        self.boost_badge=tk.Label(bar,text="",bg="#0a1020",fg=ORANGE,font=FONT_S); self.boost_badge.pack(side=tk.LEFT,padx=4)
        tk.Button(bar,text="CAMERA",bg="#001014",fg=TEAL,font=FONT_S,command=self._open_camera).pack(side=tk.RIGHT,padx=3)

    def _on_eng(self,*a):
        name=self.eng_var.get()
        key=next((k for k,v in ENGINE_PROFILES.items() if v["name"]==name),"i4_na")
        self.engine.set_profile(key); self.eng_badge.config(text=name)
        if hasattr(self,"_cyl_frame"): self._rebuild_cyl_kill()

    def _build_status_bar(self):
        sb=tk.Frame(self,bg="#050a0f"); sb.pack(fill=tk.X)
        SBKEYS=[("RPM",GREEN),("MAP",BLUE),("TPS",YELL),("CLT",RED),("IAT",CYAN),
                ("AFR",GREEN),("LMD",GREEN),("STFT",GREEN),("LTFT",GREEN),
                ("IGN",CYAN),("KNK",GREEN),("EGT",ORANGE),("PW",AMBER),
                ("DC%",AMBER),("OIL",TEAL),("BAT",PURP),("SPD",YELL),("BST",ORANGE)]
        self._sb={}
        for row_keys in [SBKEYS[:9],SBKEYS[9:]]:
            row=tk.Frame(sb,bg="#050a0f"); row.pack(fill=tk.X)
            for lbl,col in row_keys:
                cell=tk.Frame(row,bg="#070c14"); cell.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=1,pady=1)
                tk.Label(cell,text=lbl,bg="#070c14",fg=GRAY,font=("Courier New",FS-1)).pack()
                v=tk.Label(cell,text="---",bg="#070c14",fg=col,font=FONT); v.pack()
                v.bind("<Button-1>",lambda e,k=lbl:self._reading_popup(k))
                self._sb[lbl]=v

    def _build_dtc_bar(self):
        bar=tk.Frame(self,bg="#0a0505"); bar.pack(fill=tk.X)
        self.dtc_lbl=tk.Label(bar,text="NO DTCs",bg="#0a0505",fg=GREEN,font=FONT_S); self.dtc_lbl.pack(side=tk.LEFT,padx=5)
        self.scene_lbl=tk.Label(bar,text="WARMUP",bg="#0a0505",fg=PURP,font=FONT_S); self.scene_lbl.pack(side=tk.RIGHT,padx=5)

    def _build_tabs(self):
        nav=tk.Frame(self,bg="#050a0f"); nav.pack(fill=tk.X)
        TABS=[("MECH","mech"),("SCOPE","scope"),("CAN","can"),("TUNE","tune"),
              ("CORR","corr"),("MODULES","modules"),("SERVICE","service"),("BUILD","build"),
              ("PROBE","probe"),("SENS","sens"),("LOG","log"),("FAULT","fault"),("CONFIG","config")]
        self.content=tk.Frame(self,bg=BG); self.content.pack(fill=tk.BOTH,expand=True)
        self.tab_frames={}; self._tab_btns={}
        for label,key in TABS:
            btn=tk.Button(nav,text=label,bg=PANEL,fg="#aaccff",font=("Courier New",FS,"bold"),
                relief="flat",padx=5,pady=3,command=lambda k=key:self._show_tab(k))
            btn.pack(side=tk.LEFT); self._tab_btns[key]=btn
            self.tab_frames[key]=tk.Frame(self.content,bg=BG)
        self._show_tab("mech")

    def _show_tab(self,key):
        for k,f in self.tab_frames.items(): f.pack_forget(); self._tab_btns[k].config(bg=PANEL,fg="#aaccff")
        self.tab_frames[key].pack(fill=tk.BOTH,expand=True)
        self._tab_btns[key].config(bg="#0f3460",fg=CYAN); self._active_tab=key

    def _build_all_tabs(self):
        self._build_mech()
        self._build_scope()
        self._build_can()
        self._build_tune()
        self._build_corr()
        self._build_modules()
        self._build_service()
        self._build_build()
        self._build_probe()
        self._build_sens()
        self._build_log()
        self._build_fault()
        self._build_config()

    # ── MECH TAB ─────────────────────────────────────────────────────────────
    def _build_mech(self):
        f=self.tab_frames["mech"]
        c=tk.Frame(f,bg=PANEL,bd=1); c.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(c,text="OBD-II REQUEST",bg=PANEL,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3)
        r1=tk.Frame(c,bg=PANEL); r1.pack(fill=tk.X,padx=2)
        for nm,pid in [("RPM","0C"),("Speed","0D"),("CLT","05"),("IAT","0F"),("Load","04"),
                       ("TPS","11"),("MAP","0B"),("O2","14"),("Knock","2D"),("VIN","M9")]:
            tk.Button(r1,text=nm,bg="#0f3460",fg=WHITE,font=FONT_S,command=lambda p=pid,n=nm:self._obd(p,n)).pack(side=tk.LEFT,padx=1,pady=2)
        r2=tk.Frame(c,bg=PANEL); r2.pack(fill=tk.X,padx=2,pady=2)
        tk.Button(r2,text="Active DTCs",bg="#001828",fg=TEAL,font=FONT_S,command=lambda:self._dtc_read(3)).pack(side=tk.LEFT,padx=1)
        tk.Button(r2,text="Pending",bg="#001828",fg=TEAL,font=FONT_S,command=lambda:self._dtc_read(7)).pack(side=tk.LEFT,padx=1)
        tk.Button(r2,text="CLEAR DTCs",bg="#2a0000",fg=RED,font=FONT_S,command=self._dtc_clear).pack(side=tk.LEFT,padx=1)
        tk.Button(r2,text="Freeze Frame",bg="#001828",fg=TEAL,font=FONT_S,command=self._freeze).pack(side=tk.LEFT,padx=1)
        self.ap_var=tk.BooleanVar()
        tk.Checkbutton(r2,text="Auto-Poll",variable=self.ap_var,bg=PANEL,fg=CYAN,font=FONT_S,selectcolor=DARK,
            command=lambda:setattr(self.can,"autopoll",self.ap_var.get())).pack(side=tk.LEFT,padx=5)
        self.obd_out=tk.Text(f,height=4,bg=DARK,fg=CYAN,font=FONT_S,wrap=tk.WORD); self.obd_out.pack(fill=tk.X,padx=3,pady=2)
        gc=tk.Frame(f,bg=PANEL,bd=1); gc.pack(fill=tk.BOTH,expand=True,padx=3,pady=2)
        tk.Label(gc,text="LIVE VALUES",bg=PANEL,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3)
        gf=tk.Frame(gc,bg=PANEL); gf.pack(fill=tk.BOTH,expand=True); self._lv={}
        LV=[("RPM","rpm",GREEN),("MAP kPa","map_kpa",BLUE),("TPS%","tps",YELL),
            ("CLT C","clt",RED),("IAT C","iat",CYAN),("AFR","afr",GREEN),
            ("Lambda","lam",GREEN),("STFT%","stft",GREEN),("LTFT%","ltft",GREEN),
            ("IGN deg","adv",CYAN),("Knock","kret",GREEN),("EGT C","egt",ORANGE),
            ("PW ms","pw",AMBER),("DC%","dc",AMBER),("Oil psi","oil",TEAL),
            ("Batt V","batt",PURP),("Speed","spd",YELL),("Boost","boost_psi",ORANGE)]
        for i,(lbl,attr,col) in enumerate(LV):
            cell=tk.Frame(gf,bg=DARK,bd=1); cell.grid(row=i//6,column=i%6,padx=1,pady=1,sticky="nsew")
            gf.columnconfigure(i%6,weight=1)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=("Courier New",FS-1)).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=col,font=FONT); v.pack()
            self._lv[lbl]=(v,attr)

    def _obd(self,pid,name):
        e=self.engine
        vals={"0C":str(round(e.rpm))+" RPM","0D":str(round(e.spd))+" km/h","05":str(round(e.clt,1))+" C",
              "0F":str(round(e.iat,1))+" C","04":str(round(e.ve_live,1))+"% load","11":str(round(e.tps,1))+"%",
              "0B":str(round(e.map_kpa))+" kPa","14":"CL" if e.ego else "Open Loop",
              "2D":str(round(e.kret,1))+" deg","M9":"VIN: 1FTFW1ED3MFB12345"}
        self.obd_out.delete("1.0",tk.END)
        self.obd_out.insert(tk.END,"TX 0x7DF: 02 01 "+pid+"\nRX 0x7E8: [Resp]\n  "+name+": "+vals.get(pid,"N/A"))

    def _dtc_read(self,mode):
        e=self.engine; dtcs=e.active_dtcs if mode==3 else e.stored_dtcs
        txt="Mode 0"+str(mode)+": "+(" ".join(d[0] for d in dtcs) if dtcs else "No DTCs")
        if dtcs: txt+="\n"+"\n".join("  "+d[0]+" - "+d[1] for d in dtcs)
        self.obd_out.delete("1.0",tk.END); self.obd_out.insert(tk.END,txt)

    def _dtc_clear(self):
        self.engine.clear_dtcs(); self.obd_out.delete("1.0",tk.END); self.obd_out.insert(tk.END,"Mode 04: DTCs cleared")

    def _freeze(self):
        e=self.engine
        self.obd_out.delete("1.0",tk.END)
        self.obd_out.insert(tk.END,"FREEZE FRAME:\n RPM:"+str(round(e.rpm))+" MAP:"+str(round(e.map_kpa,1))+"kPa TPS:"+str(round(e.tps,1))+"%\n CLT:"+str(round(e.clt,1))+" AFR:"+str(round(e.afr,2))+" STFT:"+str(round(e.stft,1))+"%\n LOAD:"+str(round(e.ve_live,1))+"% BATT:"+str(round(e.batt,2))+"V")

    # ── SCOPE TAB ────────────────────────────────────────────────────────────
    def _build_scope(self):
        f=self.tab_frames["scope"]
        ctrl=tk.Frame(f,bg=BG); ctrl.pack(fill=tk.X,padx=3,pady=2)
        sigs=list(ScopeGen.SIGS.keys())
        tk.Label(ctrl,text="CH1:",bg=BG,fg=GREEN,font=FONT_S).pack(side=tk.LEFT)
        self.ch1=tk.StringVar(value=sigs[0])
        ttk.Combobox(ctrl,textvariable=self.ch1,values=sigs,width=16,font=FONT_S,state="readonly").pack(side=tk.LEFT,padx=2)
        tk.Label(ctrl,text="CH2:",bg=BG,fg=AMBER,font=FONT_S).pack(side=tk.LEFT)
        self.ch2=tk.StringVar(value=sigs[2])
        ttk.Combobox(ctrl,textvariable=self.ch2,values=["--"]+sigs,width=16,font=FONT_S,state="readonly").pack(side=tk.LEFT,padx=2)
        tk.Button(ctrl,text="Pop-Out",bg="#001828",fg=CYAN,font=FONT_S,command=lambda:self._scope_popup()).pack(side=tk.LEFT,padx=3)
        self.crank_lbl=tk.Label(ctrl,text="Pattern: 60-2",bg=BG,fg=PURP,font=FONT_S); self.crank_lbl.pack(side=tk.LEFT,padx=5)
        if MPL:
            fig=Figure(figsize=(5,2.5),dpi=80,facecolor=DARK)
            self._sc_ax=fig.add_subplot(111,facecolor=DARK)
            self._sc_cv=FigureCanvasTkAgg(fig,master=f)
            self._sc_cv.get_tk_widget().pack(fill=tk.BOTH,expand=True,padx=3,pady=2)
        else:
            tk.Label(f,text="Install matplotlib for scope display",bg=BG,fg=GRAY,font=FONT_S).pack(expand=True)

    def _scope_popup(self):
        win=tk.Toplevel(self); win.title("Scope"); win.configure(bg=BG); win.geometry("700x350")
        sigs=list(ScopeGen.SIGS.keys())
        ctrl=tk.Frame(win,bg=BG); ctrl.pack(fill=tk.X)
        ch1v=tk.StringVar(value=self.ch1.get()); ch2v=tk.StringVar(value=self.ch2.get())
        tk.Label(ctrl,text="CH1:",bg=BG,fg=GREEN,font=FONT_S).pack(side=tk.LEFT,padx=2)
        ttk.Combobox(ctrl,textvariable=ch1v,values=sigs,width=16,state="readonly").pack(side=tk.LEFT)
        tk.Label(ctrl,text="CH2:",bg=BG,fg=AMBER,font=FONT_S).pack(side=tk.LEFT,padx=2)
        ttk.Combobox(ctrl,textvariable=ch2v,values=["--"]+sigs,width=16,state="readonly").pack(side=tk.LEFT)
        tk.Button(ctrl,text="X",bg="#2a0000",fg=RED,font=FONT_S,command=win.destroy).pack(side=tk.RIGHT,padx=2)
        if MPL:
            fig=Figure(figsize=(7,3.5),dpi=80,facecolor=DARK)
            ax=fig.add_subplot(111,facecolor=DARK)
            cv=FigureCanvasTkAgg(fig,master=win); cv.get_tk_widget().pack(fill=tk.BOTH,expand=True)
            snaps=[]; snap_btn=tk.Button(ctrl,text="Snapshot",bg="#001828",fg=CYAN,font=FONT_S)
            snap_btn.pack(side=tk.LEFT,padx=2)
            def snap():
                d1=list(self.scope.bufs.get(ch1v.get(),[])); d2=list(self.scope.bufs.get(ch2v.get(),[]))
                snaps.append((d1,d2)); snap_btn.config(text="Snap("+str(len(snaps))+")")
            snap_btn.config(command=snap)
            def upd():
                if not win.winfo_exists(): return
                ax.clear(); ax.set_facecolor(DARK); ax.tick_params(colors=GRAY,labelsize=6); ax.spines[:].set_color(DIM)
                ch1=ch1v.get(); ch2=ch2v.get()
                if ch1 in self.scope.bufs:
                    d=list(self.scope.bufs[ch1])
                    if d: ax.plot(d,color=ScopeGen.SIGS[ch1]["col"],lw=1.2,label=ch1)
                if ch2 and ch2!="--" and ch2 in self.scope.bufs:
                    d2=list(self.scope.bufs[ch2])
                    if d2: ax.plot(d2,color=ScopeGen.SIGS[ch2]["col"],lw=1.2,label=ch2,alpha=0.8)
                for sn in snaps[-2:]:
                    if sn[0]: ax.plot(sn[0],lw=0.6,alpha=0.35,color=GRAY)
                ax.legend(fontsize=6,facecolor=DARK,labelcolor=WHITE,loc="upper right"); cv.draw_idle()
                win.after(80,upd)
            upd()

    # ── CAN/LIN TAB ──────────────────────────────────────────────────────────
    def _build_can(self):
        f=self.tab_frames["can"]
        nav=tk.Frame(f,bg=BG); nav.pack(fill=tk.X,padx=3,pady=2)
        self._can_subs={}; self._can_btns={}
        for lbl,k in [("J1939","j1939"),("OBD","obd"),("LIN","lin"),("UDS","uds"),("PROTO ANLYZ","proto")]:
            btn=tk.Button(nav,text=lbl,bg=PANEL,fg=WHITE,font=FONT_S,command=lambda kk=k:self._can_sub(kk))
            btn.pack(side=tk.LEFT,padx=1); self._can_btns[k]=btn
            sf=tk.Frame(f,bg=BG); self._can_subs[k]=sf
        self._build_can_j1939(); self._build_can_obd(); self._build_can_lin(); self._build_can_uds(); self._build_can_proto()
        self._can_sub("j1939")

    def _can_sub(self,k):
        for kk,ff in self._can_subs.items(): ff.pack_forget(); self._can_btns[kk].config(bg=PANEL)
        self._can_subs[k].pack(fill=tk.BOTH,expand=True); self._can_btns[k].config(bg="#0f3460")

    def _build_can_j1939(self):
        f=self._can_subs["j1939"]
        ctrl=tk.Frame(f,bg=BG); ctrl.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(ctrl,text="J1939 250kbps 29-bit — Heavy Duty",bg=BG,fg=ORANGE,font=FONT_S).pack(side=tk.LEFT)
        cols=("Time","ID","PGN","Name","Data","Decoded")
        self._j_tv=ttk.Treeview(f,columns=cols,show="headings",height=12)
        for c in cols: self._j_tv.heading(c,text=c); self._j_tv.column(c,width=90 if c=="Data" else 60)
        self._j_tv.pack(fill=tk.BOTH,expand=True,padx=3,pady=2)

    def _build_can_obd(self):
        f=self._can_subs["obd"]
        ctrl=tk.Frame(f,bg=BG); ctrl.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(ctrl,text="OBD-II 500kbps 11-bit — Mode/PID",bg=BG,fg=GREEN,font=FONT_S).pack(side=tk.LEFT)
        self.ap2=tk.BooleanVar()
        tk.Checkbutton(ctrl,text="Auto-Poll",variable=self.ap2,bg=BG,fg=CYAN,font=FONT_S,selectcolor=DARK,
            command=lambda:setattr(self.can,"autopoll",self.ap2.get())).pack(side=tk.LEFT,padx=8)
        cols=("Time","ID","Dir","Data","Decoded")
        self._o_tv=ttk.Treeview(f,columns=cols,show="headings",height=12)
        for c in cols: self._o_tv.heading(c,text=c); self._o_tv.column(c,width=90)
        self._o_tv.pack(fill=tk.BOTH,expand=True,padx=3,pady=2)

    def _build_can_lin(self):
        f=self._can_subs["lin"]
        tk.Label(f,text="LIN Bus 9.6/19.2kbps — Body Modules",bg=BG,fg=CYAN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        self._lin_txt=tk.Text(f,bg=DARK,fg=CYAN,font=FONT_S,height=14,state="disabled"); self._lin_txt.pack(fill=tk.BOTH,expand=True,padx=3)

    def _build_can_uds(self):
        f=self._can_subs["uds"]
        tk.Label(f,text="UDS ISO 14229 — Unified Diagnostic Services",bg=BG,fg=TEAL,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        urow=tk.Frame(f,bg=BG); urow.pack(fill=tk.X,padx=3)
        for sid,nm in [("0x10","SessCtrl"),("0x11","ECUReset"),("0x19","ReadDTC"),
                        ("0x22","ReadDID"),("0x27","SecAccess"),("0x2E","WriteData"),
                        ("0x31","Routine"),("0x3E","TesterPres")]:
            tk.Button(urow,text=sid+"\n"+nm,bg="#001a2a",fg=CYAN,font=("Courier New",FS-1),
                width=10,command=lambda s=sid,n=nm:self._uds_svc(s,n)).pack(side=tk.LEFT,padx=1,pady=2)
        self._uds_out=tk.Text(f,height=8,bg=DARK,fg=GREEN,font=FONT_S,state="disabled"); self._uds_out.pack(fill=tk.BOTH,expand=True,padx=3,pady=3)

    def _uds_svc(self,sid,name):
        e=self.engine
        resp={"0x10":"Pos: Session changed to Ext Diag","0x11":"Pos: ECU resetting","0x19":"DTCs: "+(" ".join(d[0] for d in e.active_dtcs) or "None"),
              "0x22":"DID data: "+str(round(e.rpm))+" RPM / "+str(round(e.map_kpa,1))+" kPa","0x27":"Seed: 0x4A2B  Key: 0x8F1C — unlocked",
              "0x2E":"DID written: OK","0x31":"Routine started","0x3E":"TesterPresent: keepalive sent"}
        self._uds_out.config(state="normal"); self._uds_out.delete("1.0",tk.END)
        self._uds_out.insert(tk.END,"TX: "+sid+" ("+name+")\nRX: "+resp.get(sid,"Positive Response"))
        self._uds_out.config(state="disabled")

    def _build_can_proto(self):
        f=self._can_subs["proto"]
        ctrl=tk.Frame(f,bg=BG); ctrl.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(ctrl,text="PROTOCOL ANALYZER — unknown CAN sniff",bg=BG,fg=YELL,font=FONT_S).pack(side=tk.LEFT)
        self._cap=tk.BooleanVar()
        tk.Checkbutton(ctrl,text="CAPTURE",variable=self._cap,bg=BG,fg=GREEN,font=FONT_S,selectcolor=DARK,
            command=lambda:setattr(self.can,"capturing",self._cap.get())).pack(side=tk.LEFT,padx=4)
        tk.Button(ctrl,text="Export CSV",bg="#2a1800",fg=AMBER,font=FONT_S,command=self._proto_export).pack(side=tk.LEFT,padx=2)
        cols=("ID","D0","D1","D2","D3","D4","D5","D6","D7","Library Match")
        self._p_tv=ttk.Treeview(f,columns=cols,show="headings",height=12)
        for c in cols: self._p_tv.heading(c,text=c); self._p_tv.column(c,width=50)
        self._p_tv.pack(fill=tk.BOTH,expand=True,padx=3,pady=2)
        self._p_tv.tag_configure("match",background="#001828",foreground=GREEN)
        lib_f=tk.Frame(f,bg=PANEL,bd=1); lib_f.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(lib_f,text="Community Library:",bg=PANEL,fg=GRAY,font=FONT_S).pack(side=tk.LEFT,padx=3)
        for c in self.can.community:
            tk.Label(lib_f,text=c["id"]+" "+c["name"],bg=PANEL,fg=TEAL,font=FONT_S).pack(side=tk.LEFT,padx=5)

    def _proto_export(self):
        frames=list(self.can.proto)
        if not frames: return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if p:
            with open(p,"w",newline="") as f:
                w=csv.writer(f); w.writerow(["ID"]+["D"+str(i) for i in range(8)]+["Match"])
                for fr in frames: w.writerow([fr["id"]]+fr["data"]+[fr.get("match","")])

    # ── TUNE TAB ─────────────────────────────────────────────────────────────
    def _build_tune(self):
        f=self.tab_frames["tune"]
        nav=tk.Frame(f,bg=BG); nav.pack(fill=tk.X,padx=3,pady=2)
        self._tune_subs={}; self._tune_btns={}
        for lbl,k in [("VE","ve"),("IGN","ign"),("AFR","afr"),("BOOST","boost")]:
            btn=tk.Button(nav,text=lbl,bg=PANEL,fg=YELL,font=FONT_S,command=lambda kk=k:self._tune_sub(kk))
            btn.pack(side=tk.LEFT,padx=1); self._tune_btns[k]=btn
            self._tune_subs[k]=tk.Frame(f,bg=BG)
        for k in ["ve","ign","afr","boost"]: self._build_tune_map(self._tune_subs[k],k)
        ctrl=tk.Frame(f,bg=BG); ctrl.pack(fill=tk.X,padx=3)
        self._op_lbl=tk.Label(ctrl,text="Op-Point: ---",bg=BG,fg=GREEN,font=FONT_S); self._op_lbl.pack(side=tk.LEFT,padx=4)
        for lbl,cmd in [("RESET MAPS",self.maps.reset),("3D VIEW",lambda:self._tune_3d())]:
            tk.Button(ctrl,text=lbl,bg="#2a1800",fg=AMBER,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=2)
        self._tune_sub("ve")

    def _tune_sub(self,k):
        for kk,ff in self._tune_subs.items(): ff.pack_forget(); self._tune_btns[kk].config(bg=PANEL)
        self._tune_subs[k].pack(fill=tk.BOTH,expand=True); self._tune_btns[k].config(bg="#002a0e")

    def _build_tune_map(self,parent,mapkey):
        tbl=getattr(self.maps,mapkey)
        canvas=tk.Canvas(parent,bg=BG,highlightthickness=0)
        sb=ttk.Scrollbar(parent,orient="vertical",command=canvas.yview); canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y); canvas.pack(fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG); canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        hdr=tk.Frame(inner,bg=BG); hdr.pack(fill=tk.X)
        tk.Label(hdr,text="MAP|RPM",bg=BG,fg=GRAY,font=FONT_S,width=5).grid(row=0,column=0)
        for ci,rpm in enumerate(RPM_BINS):
            tk.Label(hdr,text=str(rpm),bg=BG,fg=GRAY,font=FONT_S,width=5).grid(row=0,column=ci+1)
        self._tune_cells={}
        for mi,kpa in enumerate(MAP_BINS):
            row=tk.Frame(inner,bg=BG); row.pack(fill=tk.X)
            tk.Label(row,text=str(kpa),bg=BG,fg=GRAY,font=FONT_S,width=5).pack(side=tk.LEFT)
            for ci in range(12):
                val=tbl[mi][ci]; col=self._map_col(val,mapkey)
                e=tk.Entry(row,bg=col,fg=WHITE if mapkey!="boost" else DARK,font=FONT_S,width=5,justify="center")
                e.insert(0,str(val)); e.pack(side=tk.LEFT,padx=1,pady=1)

    def _map_col(self,v,k):
        if k=="ve": return "#%02x%02x%02x"%(max(0,min(255,int((v-20)/88*200))),0,0) if v>60 else "#%02x%02x%02x"%(0,max(0,min(255,int(v/60*150))),0)
        if k=="ign": return "#%02x%02x%02x"%(0,max(0,min(255,int(v/45*200))),max(0,min(255,int(v/45*255))))
        if k=="afr": return "#ff2244" if v<12.5 else "#44ff88" if 14.2<v<15.2 else "#ffaa00"
        if k=="boost": return "#%02x%02x%02x"%(max(0,min(255,int(v*4))),max(0,min(255,int(v*2))),0) if v>0 else DIM
        return DARK

    def _tune_3d(self):
        if not MPL: messagebox.showinfo("Info","Install matplotlib for 3D view"); return
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        import numpy as np
        fig=plt.figure(figsize=(8,5),facecolor=DARK)
        ax=fig.add_subplot(111,projection="3d",facecolor=DARK)
        X,Y=np.meshgrid(range(12),range(9))
        Z=np.array(self.maps.ve)
        ax.plot_surface(X,Y,Z,cmap="plasma",edgecolor="none",alpha=0.9)
        ax.set_xlabel("RPM",color=GREEN); ax.set_ylabel("MAP",color=GREEN); ax.set_zlabel("VE%",color=GREEN)
        ax.tick_params(colors=GRAY); ax.set_title("VE Map 3D",color=GREEN)
        fig.patch.set_facecolor(DARK); plt.tight_layout(); plt.show()

    # ── CORRECTIONS TAB ──────────────────────────────────────────────────────
    def _build_corr(self):
        f=self.tab_frames["corr"]
        canvas=tk.Canvas(f,bg=BG,highlightthickness=0)
        sb=ttk.Scrollbar(f,orient="vertical",command=canvas.yview); canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y); canvas.pack(fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG); canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        for title,ax,data,unit in [
            ("CLT Correction",self.maps.clt_ax,self.maps.clt_corr,"% vs C"),
            ("IAT Correction",self.maps.iat_ax,self.maps.iat_corr,"% vs C"),
            ("Dead Time",self.maps.dt_v,self.maps.dt_ms,"ms vs V"),
            ("Idle RPM Target",self.maps.idle_ax,self.maps.idle_rpm,"RPM vs C"),
        ]:
            card=tk.Frame(inner,bg=PANEL,bd=1); card.pack(fill=tk.X,padx=3,pady=3)
            tk.Label(card,text=title+" ("+unit+")",bg=PANEL,fg=TEAL,font=FONT_S).pack(anchor="w",padx=3)
            row=tk.Frame(card,bg=PANEL); row.pack(fill=tk.X,padx=3)
            for x,y in zip(ax,data):
                cell=tk.Frame(row,bg=DARK); cell.pack(side=tk.LEFT,padx=2,pady=2)
                tk.Label(cell,text=str(x),bg=DARK,fg=GRAY,font=("Courier New",FS-1)).pack()
                e=tk.Entry(cell,bg=DARK,fg=AMBER,font=FONT_S,width=6,justify="center"); e.insert(0,str(y)); e.pack()

    # ── MODULES TAB ──────────────────────────────────────────────────────────
    def _build_modules(self):
        f=self.tab_frames["modules"]
        nav=tk.Frame(f,bg=BG); nav.pack(fill=tk.X,padx=3,pady=2)
        self._mod_subs={}; self._mod_btns={}
        for lbl,k in [("ABS","abs"),("SRS","srs"),("TCU","tcu"),("BCM","bcm"),("TPMS","tpms"),("HV","hv")]:
            btn=tk.Button(nav,text=lbl,bg=PANEL,fg=WHITE,font=FONT_S,command=lambda kk=k:self._mod_sub(kk))
            btn.pack(side=tk.LEFT,padx=1); self._mod_btns[k]=btn
            self._mod_subs[k]=tk.Frame(f,bg=BG)
        self._build_abs(); self._build_srs(); self._build_tcu()
        self._build_bcm(); self._build_tpms(); self._build_hv()
        self._mod_sub("abs")

    def _mod_sub(self,k):
        for kk,ff in self._mod_subs.items(): ff.pack_forget(); self._mod_btns[kk].config(bg=PANEL)
        self._mod_subs[k].pack(fill=tk.BOTH,expand=True); self._mod_btns[k].config(bg="#0f3460"); self._active_mod=k

    def _mod_panel(self,key,title,gauges,btns):
        f=self._mod_subs[key]
        tk.Label(f,text=title,bg=BG,fg=CYAN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        gf=tk.Frame(f,bg=BG); gf.pack(fill=tk.X,padx=3)
        g={}
        for i,(lbl,col) in enumerate(gauges):
            cell=tk.Frame(gf,bg=DARK,bd=1); cell.grid(row=0,column=i,padx=2,pady=2,sticky="nsew")
            gf.columnconfigure(i,weight=1)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=FONT_S).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=col,font=FONT); v.pack(); g[lbl]=v
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=3,pady=2)
        for lbl,cmd in btns:
            tk.Button(br,text=lbl,bg="#001828",fg=TEAL,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=1)
        res=tk.Text(f,height=5,bg=DARK,fg=GREEN,font=FONT_S); res.pack(fill=tk.X,padx=3,pady=2)
        return g,res

    def _build_abs(self):
        f=self._mod_subs["abs"]
        tk.Label(f,text="ABS — Anti-lock Brake System",bg=BG,fg=CYAN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        gf=tk.Frame(f,bg=BG); gf.pack(fill=tk.X,padx=3)
        self._abs_g={}
        for i,(lbl,col) in enumerate([("WS FL",GREEN),("WS FR",GREEN),("WS RL",GREEN),("WS RR",GREEN),("Pressure",BLUE),("Fault",GREEN)]):
            cell=tk.Frame(gf,bg=DARK,bd=1); cell.grid(row=0,column=i,padx=2,pady=2,sticky="nsew")
            gf.columnconfigure(i,weight=1)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=FONT_S).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=col,font=FONT); v.pack(); self._abs_g[lbl]=v
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=3,pady=2)
        self._abs_res=tk.Text(f,height=4,bg=DARK,fg=GREEN,font=FONT_S); 
        for lbl,cmd in [("Read DTCs",lambda:self._mod_dtc("abs",self._abs_res)),
                         ("Clear DTCs",lambda:self._mod_clr(self._abs_res)),
                         ("Bleed Cycle",lambda:self._bidir("abs","bleed",self._abs_res)),
                         ("Pump Test",lambda:self._bidir("abs","pump",self._abs_res))]:
            tk.Button(br,text=lbl,bg="#001828",fg=TEAL,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=1)
        self._abs_res.pack(fill=tk.X,padx=3,pady=2)

    def _build_srs(self):
        f=self._mod_subs["srs"]
        tk.Label(f,text="SRS — Supplemental Restraint System",bg=BG,fg=RED,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        tk.Label(f,text="WARNING: Always disable SRS before working near airbag components",bg="#1a0000",fg=RED,font=FONT_S).pack(fill=tk.X,padx=3)
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=3,pady=2)
        self._srs_res=tk.Text(f,height=5,bg=DARK,fg=GREEN,font=FONT_S)
        for lbl,cmd in [("Read DTCs",lambda:self._mod_dtc("srs",self._srs_res)),
                         ("Clear DTCs",lambda:self._mod_clr(self._srs_res)),
                         ("Squib Resist",lambda:self._bidir("srs","squib",self._srs_res)),
                         ("Crash Data",lambda:self._bidir("srs","crash",self._srs_res))]:
            tk.Button(br,text=lbl,bg="#1a0000",fg=RED,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=1)
        self._srs_res.pack(fill=tk.X,padx=3,pady=2)

    def _build_tcu(self):
        f=self._mod_subs["tcu"]
        tk.Label(f,text="TCU — Transmission Control",bg=BG,fg=PURP,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        gf=tk.Frame(f,bg=BG); gf.pack(fill=tk.X,padx=3); self._tcu_g={}
        for i,(lbl,col) in enumerate([("Gear",PURP),("Ratio",AMBER),("TCC",GREEN),("Line PSI",BLUE),("Temp C",RED),("Slip RPM",YELL)]):
            cell=tk.Frame(gf,bg=DARK,bd=1); cell.grid(row=0,column=i,padx=2,pady=2,sticky="nsew")
            gf.columnconfigure(i,weight=1)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=FONT_S).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=col,font=FONT); v.pack(); self._tcu_g[lbl]=v
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=3,pady=2)
        self._tcu_res=tk.Text(f,height=4,bg=DARK,fg=GREEN,font=FONT_S)
        for lbl,cmd in [("Read DTCs",lambda:self._mod_dtc("tcu",self._tcu_res)),
                         ("Clear DTCs",lambda:self._mod_clr(self._tcu_res)),
                         ("Force 1-2",lambda:self._bidir("tcu","shift1",self._tcu_res)),
                         ("TCC Lock",lambda:self._bidir("tcu","tcc",self._tcu_res)),
                         ("Line Pres",lambda:self._bidir("tcu","linepres",self._tcu_res)),
                         ("Adapt Clear",lambda:self._bidir("tcu","adapt",self._tcu_res))]:
            tk.Button(br,text=lbl,bg="#1a001a",fg=PURP,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=1)
        self._tcu_res.pack(fill=tk.X,padx=3,pady=2)

    def _build_bcm(self):
        f=self._mod_subs["bcm"]
        tk.Label(f,text="BCM — Body Control Module",bg=BG,fg=AMBER,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=3,pady=2)
        self._bcm_res=tk.Text(f,height=5,bg=DARK,fg=GREEN,font=FONT_S)
        for lbl,cmd in [("Read DTCs",lambda:self._mod_dtc("bcm",self._bcm_res)),
                         ("Clear DTCs",lambda:self._mod_clr(self._bcm_res)),
                         ("Horn",lambda:self._bidir("bcm","horn",self._bcm_res)),
                         ("Wipers",lambda:self._bidir("bcm","wipers",self._bcm_res)),
                         ("Fans",lambda:self._bidir("bcm","fan",self._bcm_res)),
                         ("PATS",lambda:self._bidir("bcm","pats",self._bcm_res))]:
            tk.Button(br,text=lbl,bg="#2a1800",fg=AMBER,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=1)
        self._bcm_res.pack(fill=tk.X,padx=3,pady=2)

    def _build_tpms(self):
        f=self._mod_subs["tpms"]
        tk.Label(f,text="TPMS — Tire Pressure Monitor",bg=BG,fg=CYAN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        gf=tk.Frame(f,bg=BG); gf.pack(fill=tk.X,padx=3); self._tpms_g={}
        for i,lbl in enumerate(["FL psi","FR psi","RL psi","RR psi"]):
            cell=tk.Frame(gf,bg=DARK,bd=1); cell.grid(row=0,column=i,padx=2,pady=2,sticky="nsew"); gf.columnconfigure(i,weight=1)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=FONT_S).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=GREEN,font=FONT); v.pack(); self._tpms_g[lbl]=v
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=3,pady=2)
        self._tpms_res=tk.Text(f,height=4,bg=DARK,fg=GREEN,font=FONT_S)
        for lbl,cmd in [("Read DTCs",lambda:self._mod_dtc("tpms",self._tpms_res)),
                         ("Relearn",lambda:self._tpms_relearn()),
                         ("Sensor IDs",lambda:self._tpms_ids())]:
            tk.Button(br,text=lbl,bg="#001828",fg=CYAN,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=1)
        self._tpms_res.pack(fill=tk.X,padx=3,pady=2)

    def _build_hv(self):
        f=self._mod_subs["hv"]
        tk.Label(f,text="HV — High Voltage System (Hybrid/EV)",bg=BG,fg=ORANGE,font=FONT_S).pack(anchor="w",padx=3,pady=2)
        tk.Label(f,text="CAUTION: HV system — orange cables, qualified technicians only",bg="#1a0500",fg=ORANGE,font=FONT_S).pack(fill=tk.X,padx=3)
        gf=tk.Frame(f,bg=BG); gf.pack(fill=tk.X,padx=3); self._hv_g={}
        for i,(lbl,col) in enumerate([("HV Volts",ORANGE),("SOC%",GREEN),("HV Amps",CYAN),("HV Temp",RED),("MG1 RPM",PURP),("MG2 RPM",PURP)]):
            cell=tk.Frame(gf,bg=DARK,bd=1); cell.grid(row=0,column=i,padx=2,pady=2,sticky="nsew"); gf.columnconfigure(i,weight=1)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=FONT_S).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=col,font=FONT); v.pack(); self._hv_g[lbl]=v
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=3,pady=2)
        self._hv_res=tk.Text(f,height=5,bg=DARK,fg=GREEN,font=FONT_S)
        for lbl,cmd in [("Read DTCs",lambda:self._mod_dtc("hv",self._hv_res)),
                         ("HV Ready",lambda:self._bidir("hv","hvready",self._hv_res)),
                         ("Cell Bal",lambda:self._bidir("hv","hvbal",self._hv_res)),
                         ("MG1 Test",lambda:self._bidir("hv","mg1",self._hv_res)),
                         ("MG2 Test",lambda:self._bidir("hv","mg2",self._hv_res))]:
            tk.Button(br,text=lbl,bg="#2a1000",fg=ORANGE,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=1)
        self._hv_res.pack(fill=tk.X,padx=3,pady=2)

    def _mod_dtc(self,mod,tb):
        e=self.engine; dtcs=e.active_dtcs
        pfx={"abs":"C","srs":"B"}.get(mod,"P")
        rel=[d for d in dtcs if d[0].startswith(pfx)] if mod in ("abs","srs") else dtcs
        tb.delete("1.0",tk.END); tb.insert(tk.END,"\n".join(d[0]+": "+d[1] for d in rel) or mod.upper()+" OK — No DTCs")

    def _mod_clr(self,tb):
        tb.delete("1.0",tk.END); tb.insert(tk.END,"DTCs cleared — retest to confirm")

    def _bidir(self,mod,action,tb):
        e=self.engine
        resp={("abs","bleed"):"Bleed: FL-FR-RL-RR, pump cycling 50Hz",
              ("abs","pump"):"Pump test: 12V applied, current 3.2A",
              ("srs","squib"):"Squib resistance: Drv 2.8ohm Pass 2.9ohm (spec 1.5-5ohm)",
              ("srs","crash"):"Crash data: No events recorded",
              ("tcu","shift1"):"SS-A energised -- 1>2 shift forced",
              ("tcu","tcc"):"TCC lock commanded -- >45kph required",
              ("tcu","linepres"):"Line pressure: "+str(round(e.trans.get("li",70)+(e.tps/100)*(e.trans.get("ld",140)-e.trans.get("li",70))))+" psi",
              ("tcu","adapt"):"Shift adapts cleared -- 20 gentle cycles to relearn",
              ("bcm","horn"):"Horn relay: 200ms pulse sent",
              ("bcm","wipers"):"Wiper: full sweep cycle",
              ("bcm","fan"):"Fan relay: stage1 ON > stage2 ON > OFF",
              ("bcm","pats"):"PATS: transponder present -- key programmed",
              ("hv","hvready"):"HV: "+("READY "+str(round(e.hv_voltage,1))+"V" if e.hv_voltage>100 else "NOT READY"),
              ("hv","hvbal"):"Cell balance: "+str(round(e.hv_soc))+"% SOC -- scanning modules",
              ("hv","mg1"):"MG1: "+str(round(e.mg1_rpm))+" RPM nominal",
              ("hv","mg2"):"MG2: "+str(round(e.mg2_rpm))+" RPM -- drive motor"}
        msg=resp.get((mod,action),"["+action+"] sent to "+mod.upper())
        tb.delete("1.0",tk.END); tb.insert(tk.END,msg)

    def _tpms_relearn(self):
        self._tpms_res.delete("1.0",tk.END)
        self._tpms_res.insert(tk.END,"Relearn active -- drive >25kph for 10 min\nFL > FR > RL > RR sequence\n433MHz RF, sensors wake at rolling speed")

    def _tpms_ids(self):
        self._tpms_res.delete("1.0",tk.END)
        self._tpms_res.insert(tk.END,"FL: 0xA3B2C1 -- 32.0 psi\nFR: 0xA3B2C2 -- 32.0 psi\nRL: 0xB4C3D1 -- 31.0 psi\nRR: 0xB4C3D2 -- 31.0 psi")

    # ── SERVICE TAB ──────────────────────────────────────────────────────────
    def _build_service(self):
        f=self.tab_frames["service"]
        nav=tk.Frame(f,bg=BG); nav.pack(fill=tk.X,padx=3,pady=2)
        self._svc_subs={}; self._svc_btns={}
        for lbl,k in [("GENERIC","generic"),("BMW","bmw"),("FORD","ford"),("GM","gm"),("TOYOTA","toyota"),("VW/AUDI","vw"),("HD","hd")]:
            btn=tk.Button(nav,text=lbl,bg=PANEL,fg=WHITE,font=FONT_S,command=lambda kk=k:self._svc_sub(kk))
            btn.pack(side=tk.LEFT,padx=1); self._svc_btns[k]=btn; self._svc_subs[k]=tk.Frame(f,bg=BG)
        self._svc_sub("generic")

    def _svc_sub(self,k):
        for kk,ff in self._svc_subs.items(): ff.pack_forget(); self._svc_btns[kk].config(bg=PANEL)
        self._svc_subs[k].pack(fill=tk.BOTH,expand=True); self._svc_btns[k].config(bg="#0f3460")
        self._build_svc_content(self._svc_subs[k],k)

    def _build_svc_content(self,parent,k):
        for w in parent.winfo_children(): w.destroy()
        canvas=tk.Canvas(parent,bg=BG,highlightthickness=0)
        sb=ttk.Scrollbar(parent,orient="vertical",command=canvas.yview); canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y); canvas.pack(fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG); canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        for name,cmd,desc in self.SVC.get(k,[]):
            card=tk.Frame(inner,bg=PANEL,bd=1); card.pack(fill=tk.X,padx=3,pady=2)
            tk.Label(card,text=name,bg=PANEL,fg=TEAL,font=FONT_S).pack(anchor="w",padx=3)
            tk.Label(card,text=cmd,bg=PANEL,fg=GRAY,font=("Courier New",FS-1)).pack(anchor="w",padx=5)
            tk.Label(card,text=desc,bg=PANEL,fg=WHITE,font=("Courier New",FS-1)).pack(anchor="w",padx=5,pady=(0,2))
            res=tk.Label(card,text="",bg=DARK,fg=GREEN,font=FONT_S,anchor="w"); res.pack(fill=tk.X,padx=3,pady=2)
            tk.Button(card,text="EXECUTE  "+name,bg="#001828",fg=TEAL,font=FONT_S,
                command=lambda r=res,n=name,c=cmd:self._run_svc(r,n,c)).pack(fill=tk.X,padx=3,pady=(0,3))

    def _run_svc(self,lbl,name,cmd):
        lbl.config(text="Executing: "+name+"\n> "+cmd+"\n< Positive Response [DEMO]")
        self.after(800,lambda:lbl.config(text=lbl.cget("text")+"\n[OK] Cycle ignition and retest"))

    # ── BUILD TAB ────────────────────────────────────────────────────────────
    TRIGGER_PATS={"60-2":"Toyota/Ford/GM -- most common","36-1":"Diesel CRDI VAG TDI",
                  "58x":"GM LS/LT -- reluctor wheel","4+1":"Early TBI systems","Sub6+2":"Subaru EJ series",
                  "Mitsu4+2":"Mitsubishi distributor CAS","EDIS36-1":"Ford EDIS distributorless","GM7x":"HEI distributor"}
    INJECTORS={"Bosch EV1 Yellow (0280156065)":{"flow":235,"dt14":0.8},"Bosch EV14 Green (0280158040)":{"flow":440,"dt14":0.58},
               "Siemens Deka (06A906031)":{"flow":630,"dt14":0.65},"Denso 550cc (23250-46090)":{"flow":550,"dt14":0.62},
               "FIC 1650cc High-Z":{"flow":1650,"dt14":0.45},"Denso CRDI Common Rail":{"flow":0,"dt14":0}}

    def _build_build(self):
        f=self.tab_frames["build"]
        nav=tk.Frame(f,bg=BG); nav.pack(fill=tk.X,padx=3,pady=2)
        self._bld_subs={}; self._bld_btns={}
        for lbl,k in [("ECU CONFIG","ecu"),("TRIGGER","trigger"),("INJECTORS","inj"),("TRANS","trans"),("SCHEMA","schema")]:
            btn=tk.Button(nav,text=lbl,bg=PANEL,fg=GREEN,font=FONT_S,command=lambda kk=k:self._bld_sub(kk))
            btn.pack(side=tk.LEFT,padx=1); self._bld_btns[k]=btn; self._bld_subs[k]=tk.Frame(f,bg=BG)
        self._bld_sub("ecu")

    def _bld_sub(self,k):
        for kk,ff in self._bld_subs.items(): ff.pack_forget(); self._bld_btns[kk].config(bg=PANEL)
        self._bld_subs[k].pack(fill=tk.BOTH,expand=True); self._bld_btns[k].config(bg="#002a0e")
        self._populate_bld(self._bld_subs[k],k)

    def _populate_bld(self,parent,k):
        for w in parent.winfo_children(): w.destroy()
        canvas=tk.Canvas(parent,bg=BG,highlightthickness=0)
        sb=ttk.Scrollbar(parent,orient="vertical",command=canvas.yview); canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y); canvas.pack(fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG); canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        p=self.engine.profile
        if k=="ecu":
            tk.Label(inner,text="ECU CONFIG -- SPEEDUINO COMPATIBLE",bg=BG,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
            fields=[("Cylinders",str(p["cyl"])),("Displacement cc",str(int(p["disp"]*1000))),
                    ("CR",str(p["cr"])+":1"),("Firing Order","-".join(str(x) for x in p["fir"])),
                    ("Trigger",p["pat"]),("Injection",p["inj"]),("Idle Ctrl","PWM IAC"),
                    ("Boost","PWM" if p["turbo"] else "N/A"),("Wideband","AEM 0-5V"),("Flex Fuel","Disabled")]
            for lbl,default in fields:
                row=tk.Frame(inner,bg=BG); row.pack(fill=tk.X,padx=5,pady=1)
                tk.Label(row,text=lbl,bg=BG,fg=GRAY,font=FONT_S,width=18,anchor="w").pack(side=tk.LEFT)
                e=tk.Entry(row,bg=DARK,fg=AMBER,font=FONT_S,width=20); e.insert(0,default); e.pack(side=tk.LEFT,padx=3)
            res=tk.Label(inner,text="",bg=DARK,fg=GREEN,font=FONT_S,justify="left"); res.pack(fill=tk.X,padx=5,pady=3)
            tk.Button(inner,text="VALIDATE CONFIG",bg="#002a0e",fg=GREEN,font=FONT_S,
                command=lambda:res.config(text="PASS -- cyl/trigger/inj sizing compatible")).pack(padx=5,pady=2,anchor="w")
        elif k=="trigger":
            tk.Label(inner,text="TRIGGER PATTERN LIBRARY",bg=BG,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
            for pat,desc in self.TRIGGER_PATS.items():
                card=tk.Frame(inner,bg=PANEL,bd=1); card.pack(fill=tk.X,padx=3,pady=1)
                tk.Label(card,text=pat,bg=PANEL,fg=CYAN,font=FONT_S,width=14,anchor="w").pack(side=tk.LEFT,padx=3)
                tk.Label(card,text=desc,bg=PANEL,fg=WHITE,font=FONT_S).pack(side=tk.LEFT,padx=3)
        elif k=="inj":
            tk.Label(inner,text="INJECTOR DATABASE",bg=BG,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
            for name,data in self.INJECTORS.items():
                card=tk.Frame(inner,bg=PANEL,bd=1); card.pack(fill=tk.X,padx=3,pady=1)
                tk.Label(card,text=name,bg=PANEL,fg=AMBER,font=FONT_S).pack(anchor="w",padx=3)
                info="Flow: "+str(data["flow"])+"cc/min  Dead time @14V: "+str(data["dt14"])+"ms" if data["flow"] else "Common rail -- pressure-based control"
                tk.Label(card,text=info,bg=PANEL,fg=GRAY,font=("Courier New",FS-1)).pack(anchor="w",padx=5)
            tk.Label(inner,text="DEAD TIME CALC",bg=BG,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3,pady=(6,2))
            row=tk.Frame(inner,bg=BG); row.pack(fill=tk.X,padx=3)
            inj_v=tk.StringVar(value=list(self.INJECTORS.keys())[0])
            ttk.Combobox(row,textvariable=inj_v,values=list(self.INJECTORS.keys()),width=28,state="readonly").pack(side=tk.LEFT,padx=2)
            v_v=tk.DoubleVar(value=13.5)
            tk.Entry(row,textvariable=v_v,bg=DARK,fg=AMBER,font=FONT_S,width=6).pack(side=tk.LEFT,padx=2)
            tk.Label(row,text="V",bg=BG,fg=GRAY,font=FONT_S).pack(side=tk.LEFT)
            dt_res=tk.Label(inner,text="",bg=DARK,fg=GREEN,font=FONT_S,anchor="w"); dt_res.pack(fill=tk.X,padx=3,pady=2)
            def calc_dt():
                inj=self.INJECTORS.get(inj_v.get(),{})
                if not inj.get("flow"): dt_res.config(text="Common rail -- no dead time calc"); return
                dt=inj["dt14"]+(14-v_v.get())*0.08
                dt_res.config(text=inj_v.get()+"\n@ "+str(v_v.get())+"V  Dead time: "+str(round(dt,3))+"ms  Flow: "+str(inj["flow"])+"cc/min")
            tk.Button(row,text="CALC",bg="#2a1800",fg=AMBER,font=FONT_S,command=calc_dt).pack(side=tk.LEFT,padx=3)
        elif k=="trans":
            tk.Label(inner,text="TRANSMISSION VARIANTS",bg=BG,fg=PURP,font=FONT_S).pack(anchor="w",padx=3,pady=2)
            for tk2,tp in TRANS_PROFILES.items():
                card=tk.Frame(inner,bg=PANEL,bd=1); card.pack(fill=tk.X,padx=3,pady=2)
                tk.Label(card,text=tp["name"],bg=PANEL,fg=PURP,font=FONT_S).pack(anchor="w",padx=3)
                ratstr=" / ".join(str(r) for r in tp["ratios"])
                tk.Label(card,text="Gears:"+str(tp["gears"] or "CVT")+"  Ratios:"+ratstr+"  Final:"+str(tp["final"]),bg=PANEL,fg=GRAY,font=("Courier New",FS-1)).pack(anchor="w",padx=5)
            tk.Label(inner,text="NOTE: Toyota EVT uses planetary gearset -- NOT diameter-change CVT\nAllison: separate J1939 250kbps -- not standard OBD",bg=BG,fg=BLUE,font=("Courier New",FS-1),justify="left").pack(padx=5,pady=4)
        elif k=="schema":
            tk.Label(inner,text="ECU SCHEMATIC TEMPLATES",bg=BG,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3,pady=2)
            schemas=[("4-Cyl PFI Petrol (Speeduino UA4C)","4x inj, 4x coil, CKP 60-2, CMP, CLT, IAT, TPS, MAP, O2, IAC"),
                     ("6-Cyl DI Turbo","6x DI hi-press, 6x COP, boost sol, WBO2, flex fuel"),
                     ("Diesel CRDI","Hi-press rail, metering valve, inj solenoid/piezo, glow, EGR"),
                     ("V8 NA Carb-to-EFI","8x MPFI, distributor trigger, O2, alpha-N TPS map"),
                     ("TCU 6-speed Auto","3x shift sol, TCC sol, line press PWM, TFT sensor, shaft speeds")]
            for name,desc in schemas:
                card=tk.Frame(inner,bg=PANEL,bd=1); card.pack(fill=tk.X,padx=3,pady=2)
                tk.Label(card,text=name,bg=PANEL,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3)
                tk.Label(card,text=desc,bg=PANEL,fg=GRAY,font=("Courier New",FS-1)).pack(anchor="w",padx=5,pady=(0,3))

    # ── PROBE TAB ────────────────────────────────────────────────────────────
    def _build_probe(self):
        f=self.tab_frames["probe"]
        vc=tk.Frame(f,bg=PANEL,bd=1); vc.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(vc,text="POWER PROBE",bg=PANEL,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3)
        self._probe_v=tk.Label(vc,text="12.6 V",bg=DARK,fg=GREEN,font=("Courier New",22,"bold")); self._probe_v.pack(fill=tk.X,padx=5,pady=3)
        gg=tk.Frame(vc,bg=PANEL); gg.pack(fill=tk.X,padx=3,pady=3); self._probe_g={}
        for lbl,col in [("AMPS",CYAN),("OHMS",AMBER),("HZ",PURP),("DUTY%",YELL)]:
            cell=tk.Frame(gg,bg=DARK,bd=1); cell.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=2)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=FONT_S).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=col,font=FONT); v.pack(); self._probe_g[lbl]=v
        mc=tk.Frame(f,bg=PANEL,bd=1); mc.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(mc,text="TEST MODE",bg=PANEL,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3)
        mr=tk.Frame(mc,bg=PANEL); mr.pack(fill=tk.X,padx=3,pady=2)
        for lbl,mode,bg,fg in [("BAT+","batt","#002a0e",GREEN),("GND","gnd",PANEL,GRAY),("Continuity","cont","#2a1800",AMBER),
                                ("Short-GND","sgnd","#2a0000",RED),("Short-PWR","spwr","#2a1000",ORANGE),
                                ("Injector","inj","#0f3460",CYAN),("PWM","pwm","#1a0028",PURP),("Relay","relay","#001a14",TEAL)]:
            tk.Button(mr,text=lbl,bg=bg,fg=fg,font=FONT_S,command=lambda m=mode:self._probe_mode(m)).pack(side=tk.LEFT,padx=1,pady=1)
        self._probe_res=tk.Text(mc,height=3,bg=DARK,fg=GREEN,font=FONT_S); self._probe_res.pack(fill=tk.X,padx=3,pady=2)
        ac=tk.Frame(f,bg=PANEL,bd=1); ac.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(ac,text="COMPONENT ACTIVATION",bg=PANEL,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3)
        ar=tk.Frame(ac,bg=PANEL); ar.pack(fill=tk.X,padx=3,pady=2)
        for lbl,comp in [("Rad Fan","fan"),("Fuel Pump","fuel_pump"),("IAC","iac"),("EVAP","purge"),("EGR","egr"),("VVT","vvt"),("Boost Sol","boost_sol"),("Glows","glow")]:
            tk.Button(ar,text=lbl,bg="#001a14",fg=TEAL,font=FONT_S,command=lambda c=comp:self._probe_actuate(c)).pack(side=tk.LEFT,padx=1,pady=1)
        self._act_res=tk.Text(ac,height=3,bg=DARK,fg=TEAL,font=FONT_S); self._act_res.pack(fill=tk.X,padx=3,pady=2)
        cc=tk.Frame(f,bg=PANEL,bd=1); cc.pack(fill=tk.X,padx=3,pady=2)
        tk.Label(cc,text="CYLINDER CONTRIBUTION TEST",bg=PANEL,fg=GREEN,font=FONT_S).pack(anchor="w",padx=3)
        self._cyl_frame=tk.Frame(cc,bg=PANEL); self._cyl_frame.pack(fill=tk.X,padx=3,pady=2)
        self._kill_lbl=tk.Label(cc,text="Kill cylinder to test contribution",bg=DARK,fg=GREEN,font=FONT_S); self._kill_lbl.pack(fill=tk.X,padx=3,pady=2)
        self._rebuild_cyl_kill()

    def _rebuild_cyl_kill(self):
        for w in self._cyl_frame.winfo_children(): w.destroy()
        p=self.engine.profile
        for i in range(p["cyl"]):
            killed=self.engine.cyl_kill[i]
            tk.Button(self._cyl_frame,text="CYL "+str(i+1),bg="#2a0000" if killed else PANEL,fg=RED if killed else WHITE,
                font=FONT_S,command=lambda ci=i:self._toggle_cyl(ci)).pack(side=tk.LEFT,padx=1)

    def _toggle_cyl(self,i):
        self.engine.cyl_kill[i]=not self.engine.cyl_kill[i]; self._rebuild_cyl_kill()
        killed=[i+1 for i,k in enumerate(self.engine.cyl_kill) if k]
        self._kill_lbl.config(text="Killed: Cyl "+str(killed) if killed else "All cylinders active")

    def _probe_mode(self,mode):
        if self._probe_cb: self.after_cancel(self._probe_cb)
        e=self.engine
        msgs={"batt":"Battery positive -- "+str(round(e.batt,3))+"V DC","gnd":"Ground ref -- check offset >0.1V",
              "cont":"Continuity -- <5ohm connected / open circuit","sgnd":"SHORT TO GROUND -- high current path",
              "spwr":"SHORT TO POWER -- circuit energised","inj":"Injector pulse -- PW "+str(round(e.pw,2))+"ms",
              "pwm":"PWM output -- variable duty IAC signal","relay":"Relay coil -- pull-in 12V hold 0.15A"}
        self._probe_res.delete("1.0",tk.END); self._probe_res.insert(tk.END,msgs.get(mode,mode))
        def upd():
            v,a,ohm,hz,dc={"batt":(e.batt,0.001,999,0,0),"gnd":(0.02,0,0.1+abs(randn()*0.05),0,0),
                "cont":(0,0,2+abs(randn()*0.5),0,0),"sgnd":(0.1,12+abs(randn()),0.8,0,0),
                "spwr":(e.batt-0.2,8+abs(randn()),1.2,0,0),"inj":(e.batt*(1-e.dc/100),0.8+randn()*0.1,14+randn()*0.5,e.rpm/120,e.dc),
                "pwm":(e.batt*0.7,0.3,40+randn(),150+randn()*5,30+math.sin(time.time())*15),
                "relay":(12 if random.random()>0.5 else 0,0.15,120+randn()*5,0,0)}.get(mode,(0,0,0,0,0))
            self._probe_v.config(text=str(round(v,3))+" V")
            self._probe_g["AMPS"].config(text=str(round(a,3)))
            self._probe_g["OHMS"].config(text="inf" if ohm>500 else str(round(ohm,1)))
            self._probe_g["HZ"].config(text=str(round(hz,1)))
            self._probe_g["DUTY%"].config(text=str(round(dc,1)))
            self._probe_cb=self.after(120,upd)
        upd()

    def _probe_actuate(self,comp):
        e=self.engine
        msgs={"fan":"Rad fan relay: stage1 ON -- check 12V at connector",
              "fuel_pump":"Fuel pump prime -- building to "+str(round(self.maps.fuel_psi))+" psi",
              "iac":"IAC/DBW step test -- observe idle RPM +/-150",
              "purge":"EVAP purge: open -- audible click, vacuum to canister",
              "egr":"EGR: commanded open -- MAP drop, rough idle","vvt":"VVT solenoid: oil pressure to phaser",
              "boost_sol":"Boost solenoid duty test -- target "+str(self.engine.env["boost_target"])+" psi",
              "glow":"Glow plugs: "+str(e.profile["cyl"])+"x -- "+str(e.profile["cyl"]*12)+"A draw"}
        self._act_res.delete("1.0",tk.END); self._act_res.insert(tk.END,msgs.get(comp,comp+" actuated"))

    # ── SENSORS TAB ──────────────────────────────────────────────────────────
    def _build_sens(self):
        f=self.tab_frames["sens"]
        gf=tk.Frame(f,bg=BG); gf.pack(fill=tk.X,padx=3,pady=2); self._sens_g={}
        items=[("Wideband O2","afr",GREEN),("Narrowband","ego",GREEN),("MAP kPa","map_kpa",BLUE),
               ("TPS%","tps",YELL),("CLT C","clt",RED),("IAT C","iat",CYAN),
               ("Batt V","batt",PURP),("Oil psi","oil",TEAL),("EGT C","egt",ORANGE),
               ("Knock","klvl",RED),("Boost","boost_psi",ORANGE),("RPM","rpm",GREEN),
               ("Speed","spd",YELL),("Gear","gear",PURP),("Glow","glow_ready",AMBER),("STFT%","stft",GREEN)]
        for i,(lbl,attr,col) in enumerate(items):
            cell=tk.Frame(gf,bg=DARK,bd=1); cell.grid(row=i//4,column=i%4,padx=2,pady=2,sticky="nsew")
            gf.columnconfigure(i%4,weight=1)
            tk.Label(cell,text=lbl,bg=DARK,fg=GRAY,font=FONT_S).pack()
            v=tk.Label(cell,text="---",bg=DARK,fg=col,font=FONT); v.pack()
            self._sens_g[lbl]=(v,attr)

    # ── LOG TAB ──────────────────────────────────────────────────────────────
    def _build_log(self):
        f=self.tab_frames["log"]
        ctrl=tk.Frame(f,bg=BG); ctrl.pack(fill=tk.X,padx=3,pady=2)
        self._log_badge=tk.Label(ctrl,text="LOGGING: OFF",bg=DARK,fg=RED,font=FONT,width=18); self._log_badge.pack(side=tk.LEFT,padx=3)
        for lbl,cmd,col in [("START",self._log_start,"#002a0e"),("STOP",self._log_stop,"#2a0000"),("CSV",self._log_save,"#2a1800"),("Clear",self._log_clear,PANEL)]:
            tk.Button(ctrl,text=lbl,bg=col,fg=GREEN if "START" in lbl else RED if "STOP" in lbl else AMBER,font=FONT_S,command=cmd).pack(side=tk.LEFT,padx=2)
        cols=("Time","RPM","MAP","TPS","CLT","IAT","AFR","STFT","LTFT","IGN","KNOCK","EGT","PW","BOOST","GEAR","SCENE")
        self._log_tv=ttk.Treeview(f,columns=cols,show="headings")
        for c in cols: self._log_tv.heading(c,text=c); self._log_tv.column(c,width=50)
        self._log_tv.pack(fill=tk.BOTH,expand=True,padx=3,pady=2)

    def _log_start(self): self.logging=True; self._log_badge.config(text="LOGGING: ON",fg=GREEN)
    def _log_stop(self): self.logging=False; self._log_badge.config(text="STOPPED ("+str(len(self.log_data))+")",fg=AMBER)
    def _log_clear(self):
        self.log_data.clear()
        for r in self._log_tv.get_children(): self._log_tv.delete(r)
        self._log_badge.config(text="LOGGING: OFF",fg=RED)
    def _log_save(self):
        if not self.log_data: return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if p:
            with open(p,"w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=self.log_data[0].keys()); w.writeheader(); w.writerows(self.log_data)

    # ── FAULT TAB ────────────────────────────────────────────────────────────
    def _build_fault(self):
        f=self.tab_frames["fault"]
        canvas=tk.Canvas(f,bg=BG,highlightthickness=0)
        sb=ttk.Scrollbar(f,orient="vertical",command=canvas.yview); canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y); canvas.pack(fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG); canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        tk.Label(inner,text="ENGINE FAULT INJECTION",bg=BG,fg=RED,font=FONT_S).pack(anchor="w",padx=3,pady=(3,1))
        self._fault_vars={}
        for attr,lbl,desc in self.FAULTS:
            row=tk.Frame(inner,bg=PANEL,bd=1); row.pack(fill=tk.X,padx=3,pady=1)
            v=tk.BooleanVar(value=False); self._fault_vars[attr]=v
            tk.Checkbutton(row,variable=v,bg=PANEL,fg=RED,selectcolor=DARK,command=lambda a=attr,vv=v:setattr(self.engine,a,vv.get())).pack(side=tk.LEFT,padx=3)
            tk.Label(row,text=lbl,bg=PANEL,fg=RED,font=FONT_S,width=22,anchor="w").pack(side=tk.LEFT)
            tk.Label(row,text=desc,bg=PANEL,fg=GRAY,font=("Courier New",FS-1)).pack(side=tk.LEFT,padx=5)
        tk.Label(inner,text="MISFIRE INJECTION",bg=BG,fg=AMBER,font=FONT_S).pack(anchor="w",padx=3,pady=(5,1))
        mr=tk.Frame(inner,bg=BG); mr.pack(fill=tk.X,padx=3)
        tk.Button(mr,text="NO MISS",bg=PANEL,fg=WHITE,font=FONT_S,command=lambda:setattr(self.engine,"fault_miss",0)).pack(side=tk.LEFT,padx=1)
        for i in range(1,9):
            tk.Button(mr,text="CYL "+str(i),bg="#2a0800",fg=AMBER,font=FONT_S,command=lambda ci=i:setattr(self.engine,"fault_miss",ci)).pack(side=tk.LEFT,padx=1)
        tk.Label(inner,text="MODULE FAULT INJECTION",bg=BG,fg=ORANGE,font=FONT_S).pack(anchor="w",padx=3,pady=(5,1))
        self._modfault_vars={}
        for mod,code,desc in self.MOD_FAULTS:
            row=tk.Frame(inner,bg=PANEL,bd=1); row.pack(fill=tk.X,padx=3,pady=1)
            v=tk.BooleanVar(value=False); self._modfault_vars[code]=v
            tk.Checkbutton(row,variable=v,bg=PANEL,fg=ORANGE,selectcolor=DARK,
                command=lambda c=code,d=desc,vv=v:self._toggle_modfault(c,d,vv.get())).pack(side=tk.LEFT,padx=3)
            tk.Label(row,text="["+mod.upper()+"] "+code,bg=PANEL,fg=ORANGE,font=FONT_S,width=16,anchor="w").pack(side=tk.LEFT)
            tk.Label(row,text=desc,bg=PANEL,fg=GRAY,font=("Courier New",FS-1)).pack(side=tk.LEFT,padx=5)
        tk.Button(inner,text="CLEAR ALL FAULTS",bg="#2a0000",fg=RED,font=FONT,command=self._clear_all_faults).pack(fill=tk.X,padx=3,pady=5)

    def _toggle_modfault(self,code,desc,active):
        if active: self.engine.active_dtcs.append((code,desc))
        else: self.engine.active_dtcs=[d for d in self.engine.active_dtcs if d[0]!=code]

    def _clear_all_faults(self):
        for attr,_,__ in self.FAULTS:
            setattr(self.engine,attr,False)
            if attr in self._fault_vars: self._fault_vars[attr].set(False)
        self.engine.fault_miss=0; self.engine.clear_dtcs()
        self.engine.kret=0; self.engine.klvl=0; self.engine.kcnt=0
        messagebox.showinfo("Faults","All faults cleared")

    # ── CONFIG TAB ───────────────────────────────────────────────────────────
    def _build_config(self):
        f=self.tab_frames["config"]
        canvas=tk.Canvas(f,bg=BG,highlightthickness=0)
        sb=ttk.Scrollbar(f,orient="vertical",command=canvas.yview); canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y); canvas.pack(fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG); canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        env=self.engine.env
        for lbl,key,mn,mx,step in [("Altitude m","altitude",0,4000,100),
                                     ("Ambient Temp C","ambient_temp",-30,50,1),
                                     ("Road Grade %","road_grade",-15,15,1),
                                     ("Boost Target psi","boost_target",0,50,1)]:
            row=tk.Frame(inner,bg=BG); row.pack(fill=tk.X,padx=5,pady=2)
            tk.Label(row,text=lbl,bg=BG,fg=GRAY,font=FONT_S,width=20,anchor="w").pack(side=tk.LEFT)
            v=tk.DoubleVar(value=env.get(key,0))
            lv=tk.Label(row,text=str(int(v.get())),bg=BG,fg=CYAN,font=FONT_S,width=5); lv.pack(side=tk.RIGHT)
            def mk(k,vv,lv2):
                def cb(val): env[k]=float(val); lv2.config(text=str(int(float(val))))
                return cb
            tk.Scale(row,from_=mn,to=mx,resolution=step,variable=v,orient=tk.HORIZONTAL,bg=BG,fg=CYAN,
                highlightthickness=0,troughcolor=DARK,command=mk(key,v,lv)).pack(side=tk.LEFT,fill=tk.X,expand=True)
        tk.Label(inner,text="FUEL TYPE",bg=BG,fg=GREEN,font=FONT_S).pack(anchor="w",padx=5,pady=(6,1))
        fv=tk.StringVar(value=env.get("fuel_type","E10"))
        for ft in ["E10","E85","91oct","93oct","98oct","diesel","B20"]:
            tk.Radiobutton(inner,text=ft,variable=fv,value=ft,bg=BG,fg=AMBER,selectcolor=DARK,font=FONT_S,
                command=lambda:env.update({"fuel_type":fv.get()})).pack(anchor="w",padx=10)
        tk.Label(inner,text="CONDITION OVERRIDE",bg=BG,fg=GREEN,font=FONT_S).pack(anchor="w",padx=5,pady=(6,1))
        cv2=tk.StringVar(value="auto")
        for cond in ["auto","warmup","idle","cruise","wot","decel","boost_test","regen"]:
            tk.Radiobutton(inner,text=cond,variable=cv2,value=cond,bg=BG,fg=YELL,selectcolor=DARK,font=FONT_S,
                command=lambda:env.update({"cond_override":cv2.get()})).pack(anchor="w",padx=10)
        bv=tk.BooleanVar(value=True)
        tk.Checkbutton(inner,text="Boost/Forced induction enabled",variable=bv,bg=BG,fg=CYAN,font=FONT_S,
            selectcolor=DARK,command=lambda:env.update({"boost_enabled":bv.get()})).pack(anchor="w",padx=5,pady=4)

    # ── CAMERA ───────────────────────────────────────────────────────────────
    def _open_camera(self):
        win=tk.Toplevel(self); win.title("Camera / Thermal"); win.configure(bg=BG); win.geometry("480x360")
        tk.Button(win,text="CLOSE",bg="#2a0000",fg=RED,font=FONT_S,command=win.destroy).pack(anchor="w",padx=3,pady=2)
        tk.Label(win,text="THERMAL SIMULATION (matplotlib) + Real camera via OS",bg=BG,fg=CYAN,font=FONT_S).pack(padx=3)
        if MPL:
            fig=Figure(figsize=(5,3.2),dpi=80,facecolor=BG)
            ax=fig.add_subplot(111,facecolor=DARK)
            cv=FigureCanvasTkAgg(fig,master=win); cv.get_tk_widget().pack(fill=tk.BOTH,expand=True)
            def upd():
                if not win.winfo_exists(): return
                ax.clear(); ax.set_facecolor(DARK); e=self.engine; W,H=60,40
                arr=[[max(0,min(300,20+max(0,120-math.sqrt((x-W*0.4)**2+(y-H*0.45)**2)*0.8)+e.clt*0.3+math.sin(x/5+e.st)*math.cos(y/5)*10*(e.klvl+0.1))) for x in range(W)] for y in range(H)]
                ax.imshow(arr,cmap="plasma",aspect="auto",origin="upper",vmin=0,vmax=300)
                ax.set_title("ENG:"+str(round(e.clt))+"C  EGT:"+str(round(e.egt))+"C",color=WHITE,fontsize=8)
                ax.axis("off"); cv.draw_idle(); win.after(100,upd)
            upd()
        else:
            tk.Label(win,text="Install matplotlib for thermal simulation",bg=BG,fg=GRAY,font=FONT_S).pack(expand=True)

    def _reading_popup(self,key):
        win=tk.Toplevel(self); win.title(key); win.configure(bg=BG); win.geometry("260x160")
        tk.Label(win,text=key,bg=BG,fg=CYAN,font=FONT).pack(padx=10,pady=5)
        tk.Label(win,text="Click scope to open full waveform view",bg=BG,fg=GRAY,font=FONT_S).pack()
        tk.Button(win,text="Open Scope",bg="#001a2a",fg=CYAN,font=FONT_S,command=lambda:[win.destroy(),self._scope_popup()]).pack(pady=5)
        tk.Button(win,text="Close",bg=PANEL,fg=WHITE,font=FONT_S,command=win.destroy).pack()

    # ── MAIN TICK ────────────────────────────────────────────────────────────
    def _tick(self):
        dt=0.08; self.engine.step(dt); self.scope.step(dt); self.can.step(dt); e=self.engine
        # Status bar
        sb={
            "RPM": (str(round(e.rpm)),   GREEN  if e.rpm<e.profile["maxr"]*0.75 else RED),
            "MAP": (str(round(e.map_kpa,1)),BLUE),
            "TPS": (str(round(e.tps,1))+"%",YELL),
            "CLT": (str(round(e.clt,1))+"C",RED if e.clt>105 else CYAN if e.clt<30 else GREEN),
            "IAT": (str(round(e.iat,1))+"C",AMBER if e.iat>60 else CYAN),
            "AFR": (str(round(e.afr,2)), RED if e.afr<12 else AMBER if e.afr>15.5 else GREEN),
            "LMD": (str(round(e.lam,3)), RED if e.lam<0.85 else AMBER if e.lam>1.1 else GREEN),
            "STFT":(str(round(e.stft,1))+"%",RED if abs(e.stft)>15 else GREEN),
            "LTFT":(str(round(e.ltft,1))+"%",RED if abs(e.ltft)>15 else GREEN),
            "IGN": (str(round(e.adv,1))+"d",RED if e.adv<5 else CYAN),
            "KNK": (str(round(e.kret,1))+"d",RED if e.kret>8 else AMBER if e.kret>3 else GREEN),
            "EGT": (str(round(e.egt))+"C", RED if e.egt>950 else AMBER if e.egt>850 else ORANGE),
            "PW":  (str(round(e.pw,2))+"ms",AMBER),
            "DC%": (str(round(e.dc,1)),  AMBER),
            "OIL": (str(round(e.oil,1))+"p",RED if e.oil<15 else TEAL),
            "BAT": (str(round(e.batt,2))+"V",RED if e.batt<11.5 else PURP),
            "SPD": (str(round(e.spd))+"k",YELL),
            "BST": (str(round(e.boost_psi,1))+"p",RED if e.boost_psi>e.profile["maxb"]*0.9 else ORANGE),
        }
        for k,(val,col) in sb.items():
            if k in self._sb: self._sb[k].config(text=val,fg=col)
        # DTC / scene
        if e.active_dtcs: self.dtc_lbl.config(text="DTCs: "+" ".join(d[0] for d in e.active_dtcs),fg=RED)
        else: self.dtc_lbl.config(text="NO DTCs",fg=GREEN)
        self.scene_lbl.config(text=e.scenario.upper())
        if e.profile["turbo"]: self.boost_badge.config(text="BOOST:"+str(round(e.boost_psi,1))+"psi")
        at=self._active_tab
        # Live values (mech)
        if at=="mech" and hasattr(self,"_lv"):
            lv_vals={"RPM":str(round(e.rpm)),"MAP kPa":str(round(e.map_kpa,1)),"TPS%":str(round(e.tps,1)),
                     "CLT C":str(round(e.clt,1)),"IAT C":str(round(e.iat,1)),"AFR":str(round(e.afr,2)),
                     "Lambda":str(round(e.lam,3)),"STFT%":str(round(e.stft,1)),"LTFT%":str(round(e.ltft,1)),
                     "IGN deg":str(round(e.adv,1)),"Knock":str(round(e.kret,1)),"EGT C":str(round(e.egt)),
                     "PW ms":str(round(e.pw,2)),"DC%":str(round(e.dc,1)),"Oil psi":str(round(e.oil,1)),
                     "Batt V":str(round(e.batt,2)),"Speed":str(round(e.spd))+" kph","Boost":str(round(e.boost_psi,1))+" psi"}
            for k,(v,attr) in self._lv.items():
                if k in lv_vals: v.config(text=lv_vals[k])
            # AFR mini scope
            if MPL and hasattr(self,"_afr_ax"):
                try:
                    ax=self._afr_ax; ax.clear(); ax.set_facecolor(DARK)
                    ax.plot(list(self.scope.bufs["Wideband O2"]),color=GREEN,lw=1.2)
                    ax.axhline(14.7,color=GRAY,lw=0.5,linestyle="--")
                    ax.tick_params(colors=GRAY,labelsize=5); ax.spines[:].set_color(DIM)
                    self._afr_cv.draw_idle()
                except: pass
        # Scope
        if at=="scope" and MPL and hasattr(self,"_sc_ax"):
            try:
                ax=self._sc_ax; ax.clear(); ax.set_facecolor(DARK)
                for ch,col in [(self.ch1.get(),GREEN),(self.ch2.get(),AMBER)]:
                    if ch and ch!="--" and ch in self.scope.bufs:
                        d=list(self.scope.bufs[ch])
                        if d: ax.plot(d,color=col,lw=1.2,label=ch)
                ax.tick_params(colors=GRAY,labelsize=6); ax.spines[:].set_color(DIM)
                ax.legend(fontsize=6,facecolor=DARK,labelcolor=WHITE,loc="upper right"); self._sc_cv.draw_idle()
            except: pass
        # CAN tables
        if at=="can":
            if hasattr(self,"_j_tv"):
                for r in self._j_tv.get_children(): self._j_tv.delete(r)
                for fr in list(self.can.j1939)[-18:]:
                    self._j_tv.insert("","end",values=(fr["t"],fr["id"],fr["pgn"],fr["name"],fr["data"],fr["decoded"]))
            if self.can.autopoll and hasattr(self,"_o_tv"):
                for r in self._o_tv.get_children(): self._o_tv.delete(r)
                for fr in list(self.can.obd)[-18:]:
                    self._o_tv.insert("","end",values=(fr["t"],fr["id"],fr["dir"],fr["data"],fr["decoded"]))
            if hasattr(self,"_lin_txt"):
                self._lin_txt.config(state="normal")
                for fr in list(self.can.lin)[-3:]:
                    self._lin_txt.insert(tk.END,fr["id"]+" "+fr["node"]+"  "+fr["data"]+"  CHK:"+fr["chk"]+"\n")
                lines=int(self._lin_txt.index("end-1c").split(".")[0])
                if lines>60: self._lin_txt.delete("1.0",str(lines-50)+".0")
                self._lin_txt.see(tk.END); self._lin_txt.config(state="disabled")
            if self.can.capturing and hasattr(self,"_p_tv"):
                for r in self._p_tv.get_children(): self._p_tv.delete(r)
                for fr in list(self.can.proto)[-22:]:
                    tag="match" if fr.get("match") else ""
                    self._p_tv.insert("","end",values=(fr["id"],)+tuple(fr["data"])+(fr.get("match",""),),tags=(tag,))
        # Tune op-point
        if at=="tune" and hasattr(self,"_op_lbl"):
            ri=idx_bin(RPM_BINS,e.rpm); mi=idx_bin(MAP_BINS,e.map_kpa)
            self._op_lbl.config(text="Op: RPM="+str(RPM_BINS[min(ri,11)])+" MAP="+str(MAP_BINS[min(mi,8)])+" VE="+str(round(e.ve_live,1))+"% IGN="+str(round(e.ign_live,1))+" PW="+str(round(e.pw,2))+"ms")
        # Modules live
        if at=="modules":
            if self._active_mod=="abs" and hasattr(self,"_abs_g"):
                spd=e.spd*1000/3600
                for lbl,val in [("WS FL",str(round(spd+randn()*0.05,2))+"m/s"),("WS FR",str(round(spd+randn()*0.05,2))+"m/s"),
                                  ("WS RL",str(round(spd+randn()*0.05,2))+"m/s"),("WS RR",str(round(spd+randn()*0.05,2))+"m/s"),
                                  ("Pressure",str(round(e.map_kpa*1.1))+"b"),("Fault","OK")]:
                    if lbl in self._abs_g: self._abs_g[lbl].config(text=val,fg=GREEN)
            if self._active_mod=="tcu" and hasattr(self,"_tcu_g"):
                tp=e.trans; g=max(1,min(tp["gears"] or 1,e.gear))
                r=tp["ratios"][min(g-1,len(tp["ratios"])-1)] if tp["ratios"] else "CVT"
                lp=tp.get("li",70)+(e.tps/100)*(tp.get("ld",140)-tp.get("li",70))
                tcc=e.spd>45 and e.tps<80
                for lbl,val,col in [("Gear","CVT" if tp["gears"]==0 else str(g)+"/"+str(tp["gears"]),PURP),
                                     ("Ratio",str(round(r,3)) if isinstance(r,float) else r,AMBER),
                                     ("TCC","LOCKED" if tcc else "OPEN",GREEN if tcc else AMBER),
                                     ("Line PSI",str(round(lp)),BLUE),("Temp C",str(round(e.clt-5)),RED),
                                     ("Slip RPM",str(round(abs(randn()*30 if tcc else randn()*80))),YELL)]:
                    if lbl in self._tcu_g: self._tcu_g[lbl].config(text=val,fg=col)
            if self._active_mod=="tpms" and hasattr(self,"_tpms_g"):
                for lbl,psi in [("FL psi",32.0),("FR psi",32.0),("RL psi",31.0),("RR psi",31.0)]:
                    v=psi+randn()*0.05; col=RED if v<28 else AMBER if v<30 else GREEN
                    if lbl in self._tpms_g: self._tpms_g[lbl].config(text=str(round(v,1)),fg=col)
            if self._active_mod=="hv" and hasattr(self,"_hv_g"):
                for lbl,val,col in [("HV Volts",str(round(e.hv_voltage,1)),ORANGE),("SOC%",str(round(e.hv_soc,1)),RED if e.hv_soc<30 else GREEN),
                                     ("HV Amps",str(round(e.hv_current,1)),CYAN),("HV Temp",str(round(e.hv_voltage/7,1)),RED),
                                     ("MG1 RPM",str(round(e.mg1_rpm)),PURP),("MG2 RPM",str(round(e.mg2_rpm)),PURP)]:
                    if lbl in self._hv_g: self._hv_g[lbl].config(text=val,fg=col)
        # Sensors
        if at=="sens" and hasattr(self,"_sens_g"):
            sv={"Wideband O2":str(round(e.afr,3))+" AFR","Narrowband":"CL" if e.ego else "OL",
                "MAP kPa":str(round(e.map_kpa,1)),"TPS%":str(round(e.tps,1)),"CLT C":str(round(e.clt,1)),
                "IAT C":str(round(e.iat,1)),"Batt V":str(round(e.batt,2)),"Oil psi":str(round(e.oil,1)),
                "EGT C":str(round(e.egt)),"Knock":str(round(e.klvl*100))+"%","Boost":str(round(e.boost_psi,1))+"psi",
                "RPM":str(round(e.rpm)),"Speed":str(round(e.spd))+"kph","Gear":str(e.gear),
                "Glow":"WARM" if e.glow_ready else "RDY" if e.profile["glow"] else "N/A","STFT%":str(round(e.stft,1))}
            for lbl,(v,_) in self._sens_g.items():
                if lbl in sv: v.config(text=sv[lbl])
        # Probe live
        if at=="probe" and hasattr(self,"_probe_v"):
            self._probe_v.config(text=str(round(e.batt,3))+" V")
        # Crank pattern label
        if at=="scope" and hasattr(self,"crank_lbl"):
            p=e.profile
            self.crank_lbl.config(text="Pattern:"+p["pat"]+" Cyls:"+str(p["cyl"])+" Firing:"+"-".join(str(x) for x in p["fir"])+" Inj:"+p["inj"])
        # Logging
        if self.logging:
            row={"Time":time.strftime("%H:%M:%S"),"RPM":str(round(e.rpm)),"MAP":str(round(e.map_kpa,1)),
                 "TPS":str(round(e.tps,1)),"CLT":str(round(e.clt,1)),"IAT":str(round(e.iat,1)),
                 "AFR":str(round(e.afr,2)),"STFT":str(round(e.stft,1)),"LTFT":str(round(e.ltft,1)),
                 "IGN":str(round(e.adv,1)),"KNOCK":str(round(e.kret,1)),"EGT":str(round(e.egt)),
                 "PW":str(round(e.pw,2)),"BOOST":str(round(e.boost_psi,1)),
                 "GEAR":"CVT" if e.trans["gears"]==0 else str(e.gear),"SCENE":e.scenario}
            self.log_data.append(row)
            if len(self.log_data)>2000: self.log_data.pop(0)
            if at=="log" and hasattr(self,"_log_tv"):
                self._log_tv.insert("","end",values=list(row.values()))
                kids=self._log_tv.get_children()
                if len(kids)>200: self._log_tv.delete(kids[0])
                self._log_tv.yview_moveto(1.0)
        self.after(80,self._tick)

# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__=="__main__":
    app=CyberKnife()
    style=ttk.Style(app)
    try: style.theme_use("clam")
    except: pass
    style.configure("TCombobox",fieldbackground=DARK,background=PANEL,foreground=WHITE,selectbackground="#0f3460",selectforeground=WHITE)
    style.configure("Treeview",background=PANEL,foreground=WHITE,rowheight=16,fieldbackground=DARK,font=("Courier New",FS))
    style.configure("Treeview.Heading",background="#0a0e14",foreground=CYAN,font=("Courier New",FS,"bold"))
    style.configure("TScrollbar",background=PANEL,troughcolor=DARK)
    app.mainloop()
