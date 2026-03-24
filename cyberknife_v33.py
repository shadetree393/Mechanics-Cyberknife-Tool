#!/usr/bin/env python3
"""MECHANIC'S CYBERKNIFE v3.3  Pydroid 3 optimised
Run: python3 cyberknife.py
Deps: pip install matplotlib numpy
"""
import tkinter as tk
from tkinter import ttk, messagebox
import random, time, threading, math
from collections import deque

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import numpy as np
    MPL = True
except Exception:
    MPL = False

BG='#0d1117';PANEL='#161b22';DARK='#0a0e14'
GREEN='#00ff88';AMBER='#ffaa00';RED='#ff4040'
BLUE='#4488ff';CYAN='#00ccff';YELL='#ffff44'
PURP='#cc55ff';WHITE='#ddeeff';GRAY='#445566';DIM='#223344'

FS=8; FM=9; FL=10; FG=11; FGG=13

class ECUMaps:
    RPM_BINS=[500,1000,1500,2000,2500,3000,3500,4000,4500,5000,5500,6000]
    MAP_BINS=[20,30,40,50,60,70,80,90,100]
    def __init__(self):
        nr=len(self.RPM_BINS);nm=len(self.MAP_BINS)
        self.ve_table=[[round(max(20,min(108,38+62*(mi/(nm-1))*(0.55+0.45*math.exp(-0.5*((ri-6)/3.2)**2))+random.uniform(-1.5,1.5))),1) for ri in range(nr)] for mi in range(nm)]
        self.ign_table=[[round(max(0,min(42,8+ri*1.8*(1-(mi/(nm-1))*0.5)+random.uniform(-0.3,0.3))),1) for ri in range(nr)] for mi in range(nm)]
        self.afr_table=[[round(12.5+(ri/(nr-1))*0.8 if mi/(nm-1)>0.85 else 15.2+(ri/(nr-1))*0.4 if mi/(nm-1)<0.25 else 14.7+random.uniform(-0.1,0.1),1) for ri in range(nr)] for mi in range(nm)]
        self.clt_ax=[-40,-20,0,20,40,60,80,90,100];self.clt_corr=[180,160,140,120,110,105,100,100,98]
        self.iat_ax=[-40,-20,0,20,40,60,80,100];self.iat_corr=[112,108,105,100,96,91,85,78]
        self.dt_v=[8,9,10,11,12,13,14,15];self.dt_ms=[1.8,1.5,1.3,1.1,0.9,0.8,0.7,0.65]
        self.idle_cax=[0,20,40,60,80,90];self.idle_rpm=[1400,1200,1000,900,850,800]
        self.req_fuel=7.2;self.soft_cut=6800;self.hard_cut=7200
        self.accel_thresh=2.5;self.accel_mult=1.6;self.accel_dur=350
        self.knock_step=2.5;self.knock_max=12.0;self.knock_rec=0.3;self.fuel_psi=43.5
    def interp2d(self,tbl,rpm,kpa):
        ri=self._idx(self.RPM_BINS,rpm);mi=self._idx(self.MAP_BINS,kpa)
        r0=max(0,ri-1);r1=min(len(self.RPM_BINS)-1,ri);m0=max(0,mi-1);m1=min(len(self.MAP_BINS)-1,mi)
        rx=max(0,min(1,(rpm-self.RPM_BINS[r0])/max(self.RPM_BINS[r1]-self.RPM_BINS[r0],1)))
        mx=max(0,min(1,(kpa-self.MAP_BINS[m0])/max(self.MAP_BINS[m1]-self.MAP_BINS[m0],1)))
        return(tbl[m0][r0]*(1-rx)*(1-mx)+tbl[m0][r1]*rx*(1-mx)+tbl[m1][r0]*(1-rx)*mx+tbl[m1][r1]*rx*mx)
    def interp1d(self,xs,ys,v):
        if v<=xs[0]:return ys[0]
        if v>=xs[-1]:return ys[-1]
        for i in range(len(xs)-1):
            if xs[i]<=v<=xs[i+1]:return ys[i]+(v-xs[i])/(xs[i+1]-xs[i])*(ys[i+1]-ys[i])
        return ys[-1]
    def _idx(self,bins,v):
        for i,b in enumerate(bins):
            if v<=b:return i
        return len(bins)-1

class EnginePhysics:
    GEARS=[0,3.5,2.0,1.35,0.98,0.75];FD=3.73;TIRE=1.98
    def __init__(self,m):
        self.m=m;self._lk=threading.Lock()
        self.rpm=800.0;self.map_kpa=35.0;self.tps=0.0
        self.clt=20.0;self.iat=25.0;self.batt=12.6
        self.gear=0;self.spd=0.0;self.afr=14.7;self.lam=1.0
        self.pw=3.0;self.dc=0.0;self.dwell=3.5;self.adv=10.0
        self.egt=600.0;self.oil=45.0;self.stft=0.0;self.ltft=0.0;self.ego=False
        self.kret=0.0;self.klvl=0.0;self.kcnt=0
        self._at=0.0;self._ptps=0.0;self._ptt=time.time()
        self.active_dtcs=[];self.stored_dtcs=[]
        self.scenario='warmup';self._st=0.0;self._rtgt=850.0
        self.fault_o2=False;self.fault_map=False;self.fault_clt=False
        self.fault_miss=0;self.fault_lean=False;self.fault_ign=False;self.fault_inj=False
        self._run=True
        threading.Thread(target=self._loop,daemon=True).start()
    def _loop(self):
        while self._run:
            time.sleep(0.08)
            with self._lk:self._step(0.08)
    def _step(self,dt):
        self._st+=dt;self._scenario();m=self.m
        self.rpm+=(self._rtgt-self.rpm)*3.0*dt+random.gauss(0,self.rpm*0.003)
        self.rpm=max(0,min(8500,self.rpm))
        mt=max(15,min(105,20+self.tps*0.78-(self.rpm/6000)*8))
        if self.fault_map:mt=50.0
        if self.fault_lean:mt+=8.0
        self.map_kpa+=(mt-self.map_kpa)*5*dt;self.map_kpa=max(15,min(105,self.map_kpa))
        ve=m.interp2d(m.ve_table,self.rpm,self.map_kpa)
        afr_tgt=m.interp2d(m.afr_table,self.rpm,self.map_kpa)
        clt_use=-40.0 if self.fault_clt else self.clt
        cc=m.interp1d(m.clt_ax,m.clt_corr,clt_use)/100
        ic=m.interp1d(m.iat_ax,m.iat_corr,self.iat)/100
        dead=m.interp1d(m.dt_v,m.dt_ms,self.batt)
        now=time.time()
        rate=(self.tps-self._ptps)/max(now-self._ptt,0.001)*0.1
        self._ptps=self.tps;self._ptt=now
        if rate>m.accel_thresh:self._at=m.accel_dur/1000
        am=1.0
        if self._at>0:
            am=1+(m.accel_mult-1)*(self._at/(m.accel_dur/1000))
            self._at=max(0,self._at-dt)
        if self.fault_inj:
            self.pw=99.0;self.dc=100.0
        else:
            et=1+(self.stft+self.ltft)/100
            self.pw=m.req_fuel*(ve/100)*(14.7/afr_tgt)*cc*ic*am*et+dead
            if self.rpm>=m.hard_cut:self.pw=0
            elif self.rpm>=m.soft_cut and random.random()<0.5:self.pw=0
            cy=120000/max(self.rpm,100);self.dc=min(100,(self.pw/cy)*100)
        ib=m.interp2d(m.ign_table,self.rpm,self.map_kpa)
        if self.fault_ign:ib=max(0,ib-10)
        risk=max(0,(ib-25)/15)*(self.map_kpa/100)*(self.rpm/6000)
        if self.fault_miss>0 and random.random()<0.15:risk+=0.4
        if random.random()<risk*0.08:
            self.kret=min(self.kret+m.knock_step,m.knock_max);self.klvl=min(1,self.klvl+0.4);self.kcnt+=1
        else:
            self.kret=max(0,self.kret-m.knock_rec*dt*10);self.klvl=max(0,self.klvl-0.05)
        self.adv=max(0,ib-self.kret)
        self.dwell=max(1.5,(3.8*(13.5/max(self.batt,8)))-self.rpm*0.0001)
        lean=1.5 if self.fault_lean else 0
        if self.fault_o2:self.afr=afr_tgt+lean+random.gauss(0,0.3);self.ego=False
        elif self.fault_inj:self.afr=random.uniform(10.2,11.5);self.ego=False
        else:self.afr=max(10,min(20,afr_tgt+lean+random.gauss(0,0.08)))
        self.lam=self.afr/14.7
        if not self.fault_o2 and self.clt>75 and self.tps<80 and self.rpm<4500:
            self.ego=True
            self.stft+=(afr_tgt-self.afr)*0.8*dt;self.stft=max(-25,min(25,self.stft))
            self.ltft+=self.stft*0.003*dt;self.ltft=max(-25,min(25,self.ltft))
        else:
            if not self.fault_o2:self.stft*=0.95
        self.egt=max(300,min(1050,450+(self.rpm/6000)*350+(self.map_kpa/100)*200+(self.lam-1)*150+random.gauss(0,5)))
        if self.fault_clt:self.clt=-40+random.gauss(0,0.5)
        elif self.clt<90:self.clt+=((self.rpm/6000)*0.4+(self.map_kpa/100)*0.2)*dt
        else:self.clt=87+random.gauss(0,1)
        self.iat+=(25+self.rpm*0.003-self.iat)*0.01*dt+random.gauss(0,0.1)
        tv=14.2 if self.rpm>900 else 12.0
        self.batt=max(10,min(15,self.batt+(tv-self.batt)*dt+random.gauss(0,0.02)))
        g=self.gear
        self.spd=self.rpm/(self.GEARS[g]*self.FD)*self.TIRE*60/1000 if 0<g<=5 else 0
        self.oil=max(0,min(90,0 if self.rpm<100 else 10+(self.rpm/6000)*60+random.gauss(0,1)))
        self._dtcs()
        if self.tps<1:self._rtgt=m.interp1d(m.idle_cax,m.idle_rpm,self.clt)+random.gauss(0,20)
    def _scenario(self):
        c=self._st%150
        if   c<20: self.scenario='warmup';self.tps=max(0,0.5+random.gauss(0,.3));self.gear=0
        elif c<40: self.scenario='cruise';self.tps=max(0,22+math.sin(self._st*.1)*5);self.gear=3;self._rtgt=2200+math.sin(self._st*.08)*300
        elif c<60: self.scenario='wot';self.tps=min(100,98+random.gauss(0,.5));self.gear=2;self._rtgt=min(7000,self._rtgt+50)
        elif c<80: self.scenario='decel';self.tps=0;self.gear=4;self._rtgt=max(800,self._rtgt-80)
        elif c<100:self.scenario='hwy';self.tps=max(0,35+random.gauss(0,2));self.gear=4;self._rtgt=3000+random.gauss(0,100)
        else:      self.scenario='idle';self.tps=max(0,.2+random.gauss(0,.2));self.gear=0;self._rtgt=850
    def _dtcs(self):
        checks=[(self.batt<11,'P0562','System Voltage Low'),(self.oil<8 and self.rpm>500,'P0520','Oil Pressure Low'),
                (self.ltft>20,'P0171','Fuel Trim Lean B1'),(self.ltft<-20,'P0172','Fuel Trim Rich B1'),
                (self.kcnt>50,'P0325','Knock Sensor'),(self.clt>115,'P0118','Coolant High'),
                (self.fault_o2,'P0131','O2 No Activity'),(self.fault_miss>0,'P030'+str(self.fault_miss),'Cyl Misfire'),
                (self.fault_clt,'P0117','CLT Sensor Low'),(self.fault_inj,'P0201','Injector Shorted')]
        codes=[d[0] for d in self.active_dtcs]
        for cond,code,desc in checks:
            if cond and code not in codes:
                self.active_dtcs.append((code,desc))
                if code not in [d[0] for d in self.stored_dtcs]:self.stored_dtcs.append((code,desc))
        keep={'P0562':self.batt<11,'P0131':self.fault_o2,'P0117':self.fault_clt,
              'P0201':self.fault_inj,'P0171':self.ltft>20,'P0172':self.ltft<-20}
        self.active_dtcs=[d for d in self.active_dtcs if keep.get(d[0],d[0].startswith('P030') and self.fault_miss>0 or True)]
    def snap(self):
        with self._lk:
            ve=self.m.interp2d(self.m.ve_table,self.rpm,self.map_kpa)
            ig=self.m.interp2d(self.m.ign_table,self.rpm,self.map_kpa)
            af=self.m.interp2d(self.m.afr_table,self.rpm,self.map_kpa)
            return dict(rpm=self.rpm,map_kpa=self.map_kpa,tps=self.tps,clt=self.clt,iat=self.iat,
                batt=self.batt,afr=self.afr,lam=self.lam,pw=self.pw,dc=self.dc,dwell=self.dwell,
                adv=self.adv,egt=self.egt,oil=self.oil,stft=self.stft,ltft=self.ltft,ego=self.ego,
                kret=self.kret,klvl=self.klvl,spd=self.spd,gear=self.gear,accel=self._at>0,
                scenario=self.scenario,active_dtcs=list(self.active_dtcs),stored_dtcs=list(self.stored_dtcs),
                ve_live=ve,ign_live=ig,afr_tgt=af)

class J1939Bus:
    PGN_MAP={61444:('EEC1','Engine Speed/Torque'),61443:('EEC2','Engine Load'),65262:('ET1','Engine Temps'),65265:('CCVS','Vehicle Speed'),65263:('EFL','Oil/Fuel Press'),65226:('DM1','Active DTCs')}
    def __init__(self,eng):
        self.eng=eng;self.msgs=deque(maxlen=200);self._run=True
        threading.Thread(target=self._loop,daemon=True).start()
    def _loop(self):
        while self._run:
            time.sleep(0.1);s=self.eng.snap();ts=time.time()
            for f in self._build(s):self.msgs.append(dict(ts=ts,**f))
    def _build(self,s):
        out=[]
        def fr(pri,pgn,sa,data,dec):
            cid='0x%08X'%((pri<<26)|(pgn<<8)|sa)
            name=self.PGN_MAP.get(pgn,('UNK','Unknown'))[1]
            out.append(dict(cid=cid,pgn='%05d'%pgn,name=name,sa='0x%02X'%sa,data=data,dec=dec))
        r=max(0,min(65535,int(s['rpm']/0.125)))
        fr(3,61444,0,'%02X %02X %02X %02X 00 00 00 00'%(0xFF,0xFF,r&0xFF,(r>>8)&0xFF),'RPM=%.0f'%s['rpm'])
        t=max(0,min(250,int(s['tps']/0.4)))
        fr(3,61443,0,'%02X %02X 00 00 00 00 00 00'%(t,int(s['map_kpa']/0.5)),'TPS=%.1f%% MAP=%.0fkPa'%(s['tps'],s['map_kpa']))
        fr(6,65262,0,'%02X %02X 00 00 00 00 00 00'%(int(s['clt']+40),int(s['iat']+40)),'CLT=%.0fC IAT=%.0fC'%(s['clt'],s['iat']))
        spd=int(s['spd']*256)
        fr(6,65265,0,'FF FF %02X %02X FF FF FF FF'%(spd&0xFF,(spd>>8)&0xFF),'SPD=%.0fkm/h'%s['spd'])
        fr(6,65263,0,'FF %02X FF FF FF FF FF FF'%int(s['oil']/0.25),'OIL=%.0fpsi'%s['oil'])
        if s['active_dtcs']:
            code,_=s['active_dtcs'][0];spn=int(code[1:])&0x3FFFF
            fr(6,65226,0,'%02X %02X %02X 00 00 00 00 00'%(1,spn&0xFF,(spn>>8)&0xFF),'DTC=%s'%code)
        return out

class OBDHandler:
    def __init__(self,eng):
        self.eng=eng;self.msgs=deque(maxlen=200);self.autopoll=False;self._run=True
        threading.Thread(target=self._poll,daemon=True).start()
    def _poll(self):
        pids=[0x0C,0x05,0x0B,0x11,0x0E,0x06,0x07];i=0
        while self._run:
            time.sleep(0.4)
            if self.autopoll:self.request(0x01,pids[i%len(pids)]);i+=1
    def request(self,mode,pid=None):
        s=self.eng.snap();ts=time.time()
        req='7DF 02 %02X %02X'%(mode,pid) if pid is not None else '7DF 01 %02X'%mode
        resp,dec=self._resp(mode,pid,s)
        self.msgs.append(dict(ts=ts,id='7DF',dir='TX',data=req,dec='REQ'))
        self.msgs.append(dict(ts=ts,id='7E8',dir='RX',data=resp,dec=dec))
        return dec
    def _resp(self,mode,pid,s):
        if mode==0x01 and pid is not None:
            tbl={0x04:('41 04 %02X'%int(s['map_kpa']/100*255),'[04h] Load=%.0f%%'%s['map_kpa']),
                 0x05:('41 05 %02X'%int(s['clt']+40),'[05h] CLT=%.0fC'%s['clt']),
                 0x06:('41 06 %02X'%int((s['stft']/100+1)*128),'[06h] STFT=%+.1f%%'%s['stft']),
                 0x07:('41 07 %02X'%int((s['ltft']/100+1)*128),'[07h] LTFT=%+.1f%%'%s['ltft']),
                 0x0B:('41 0B %02X'%int(s['map_kpa']),'[0Bh] MAP=%.0fkPa'%s['map_kpa']),
                 0x0C:('41 0C %02X %02X'%(int(s['rpm']*4)>>8,int(s['rpm']*4)&0xFF),'[0Ch] RPM=%.0f'%s['rpm']),
                 0x0D:('41 0D %02X'%int(s['spd']),'[0Dh] Speed=%.0fkm/h'%s['spd']),
                 0x0E:('41 0E %02X'%int((s['adv']+64)*2),'[0Eh] Timing=%.1fdeg'%s['adv']),
                 0x0F:('41 0F %02X'%int(s['iat']+40),'[0Fh] IAT=%.0fC'%s['iat']),
                 0x11:('41 11 %02X'%int(s['tps']/100*255),'[11h] TPS=%.1f%%'%s['tps']),
                 0x44:('41 44 %02X %02X'%(int(s['lam']*32768)>>8,int(s['lam']*32768)&0xFF),'[44h] Lambda=%.3f'%s['lam']),
                 0x5C:('41 5C %02X'%int(s['oil']+40),'[5Ch] Oil Temp')}
            if pid in tbl:return tbl[pid]
            return '7F %02X 11'%pid,'Unsupported PID'
        if mode==0x03:
            if not s['stored_dtcs']:return '43 00','No stored DTCs'
            parts=['43 %02X'%len(s['stored_dtcs'])]
            for code,_ in s['stored_dtcs'][:3]:
                n=int(code[1:]);parts.append('%02X %02X'%((n>>8)&0xFF,n&0xFF))
            return ' '.join(parts),'DTCs: '+', '.join(c for c,_ in s['stored_dtcs'])
        if mode==0x04:
            self.eng.stored_dtcs=[];self.eng.active_dtcs=[];self.eng.stft=0;self.eng.ltft=0;self.eng.kcnt=0
            return '44','DTCs cleared, trims reset'
        if mode==0x07:
            if not s['active_dtcs']:return '47 00','No pending DTCs'
            return '47 01','Pending: '+', '.join(c for c,_ in s['active_dtcs'])
        if mode==0x09 and pid==0x02:
            return '49 02 01 31 46 54 46 57 31 45 44 33 4D 46 42 31 32 33 34 35','VIN: 1FTFW1ED3MFB12345'
        return '7F %02X 11'%mode,'Unknown mode'

class ScopeGen:
    SIGS=['Crank 60-2 VR','Crank Hall','Cam Hall','Injector Primary','Ignition Primary',
          'CAN High','CAN Low','MAP Sensor','Wideband O2','Narrowband O2','TPS',
          'Battery/Alt','Injector DC','Knock Sensor','Fuel Pump PWM']
    def get(self,sig,s,n=180):
        if not MPL:return None
        rpm=max(100,s['rpm']);pw=s['pw'];dc=s['dc'];batt=s['batt'];klvl=s['klvl']
        t=np.linspace(0,2*60/rpm,n)
        if sig=='Crank 60-2 VR':
            y=np.zeros(n)
            for i,ti in enumerate(t):
                tooth=int(ti*rpm/60*60)%60
                if tooth not in(57,58,59):
                    ph=(ti*rpm/60*60)%1
                    y[i]=0.8*math.sin(ph*2*math.pi)*math.exp(-ph*3)*(1 if ph<0.5 else -0.3)
            return t,y,'V',-1.2,1.2
        if sig=='Crank Hall':
            return t,np.array([4.8 if int(ti*rpm/60*60)%60 not in(57,58,59) and int(ti*rpm/60*60*10)%10<5 else 0.2 for ti in t]),'V',-0.5,5.5
        if sig=='Cam Hall':
            return t,np.array([4.8 if int(ti*rpm/120)%2==0 else 0.2 for ti in t]),'V',-0.5,5.5
        if sig=='Injector Primary':
            cy=60/rpm;y=np.zeros(n)
            for i,ti in enumerate(t):
                ph=(ti%cy)/cy;pf=min(0.95,pw/(cy*1000))
                if ph<0.005:y[i]=12+random.gauss(0,0.2)
                elif ph<pf:y[i]=1.2+random.gauss(0,0.1)
                elif ph<pf+0.01:y[i]=-50+random.gauss(0,2)
                else:y[i]=batt+random.gauss(0,0.1)
            return t,y,'V',-55,15
        if sig=='Ignition Primary':
            cy=60/rpm;y=np.zeros(n)
            for i,ti in enumerate(t):
                ph=(ti%cy)/cy;dw=s['dwell']/1000/cy
                if ph<dw:y[i]=batt+random.gauss(0,0.1)
                elif ph<dw+0.02:y[i]=-300+random.gauss(0,10)
                else:y[i]=0.2+random.gauss(0,0.05)
            return t,y,'V',-320,15
        if sig=='CAN High':return t,np.array([3.5 if int(ti*500000)%10<4 else 2.5 for ti in t]),'V',2.0,4.0
        if sig=='CAN Low': return t,np.array([1.5 if int(ti*500000)%10<4 else 2.5 for ti in t]),'V',1.0,3.0
        if sig=='MAP Sensor':return t,np.full(n,1+(s['map_kpa']/100)*3.5)+np.random.normal(0,0.015,n),'V',0,5
        if sig=='Wideband O2':
            v=0.5+(s['lam']-0.7)*2.2
            return t,np.array([v+0.05*math.sin(ti*8)+random.gauss(0,0.01) for ti in t]),'V',0,5
        if sig=='Narrowband O2':
            v=0.85 if s['lam']<1 else 0.15
            return t,np.full(n,v)+np.random.normal(0,0.03,n),'V',-0.1,1.1
        if sig=='TPS':return t,np.full(n,0.5+(s['tps']/100)*4.0)+np.random.normal(0,0.01,n),'V',0,5
        if sig=='Battery/Alt':
            ripple=0.12*np.sin(t*120*2*math.pi) if rpm>900 else np.zeros(n)
            return t,np.full(n,batt)+ripple+np.random.normal(0,0.02,n),'V',10,15.5
        if sig=='Injector DC':
            cy=60/rpm;return t,np.array([12 if (ti%cy)/cy<(dc/100) else 0 for ti in t]),'V',-1,14
        if sig=='Knock Sensor':
            y=np.random.normal(0,0.05+klvl*0.8,n)
            if klvl>0.3:
                for k in range(0,n,n//4):
                    b=min(8,n-k);y[k:k+b]+=np.sin(np.linspace(0,4*math.pi,b))*(klvl*1.5)
            return t,y,'V',-2,2
        if sig=='Fuel Pump PWM':return t,np.array([12 if (ti*80)%1<0.65 else 0 for ti in t]),'V',-1,14
        return None

class MapEditor(tk.Frame):
    def __init__(self,parent,maps,attr,title,unit,vmin,vmax):
        super().__init__(parent,bg=PANEL)
        self.maps=maps;self.attr=attr;self.title=title;self.unit=unit;self.vmin=vmin;self.vmax=vmax;self._cells={}
        self._build()
    def _build(self):
        tbl=getattr(self.maps,self.attr)
        tk.Label(self,text='kPa|RPM',bg=PANEL,fg=GRAY,font=('Courier',7)).grid(row=0,column=0,padx=1)
        for ci,rpm in enumerate(ECUMaps.RPM_BINS):
            tk.Label(self,text=str(rpm),bg=PANEL,fg='#88aacc',font=('Courier',7)).grid(row=0,column=ci+1,padx=1)
        for mi,kpa in enumerate(ECUMaps.MAP_BINS):
            tk.Label(self,text=str(kpa),bg=PANEL,fg='#88aacc',font=('Courier',7)).grid(row=mi+1,column=0,padx=2)
            for ci in range(len(ECUMaps.RPM_BINS)):
                v=tbl[mi][ci]
                e=tk.Entry(self,width=5,font=('Courier',7),justify='center',bg=self._col(v),fg=WHITE,relief='flat',bd=1)
                e.insert(0,str(v));e.grid(row=mi+1,column=ci+1,padx=1,pady=1)
                e.bind('<FocusOut>',lambda ev,m=mi,c=ci:self._save(m,c,ev.widget))
                self._cells[(mi,ci)]=e
    def _save(self,mi,ci,w):
        try:v=float(w.get());getattr(self.maps,self.attr)[mi][ci]=round(v,1);w.config(bg=self._col(v))
        except ValueError:pass
    def _col(self,v):
        r=max(0,min(1,(v-self.vmin)/max(self.vmax-self.vmin,1)))
        if r<0.25:return '#001f4d'
        if r<0.50:return '#004d40'
        if r<0.75:return '#4d3700'
        return '#4d0000'
    def cursor(self,rpm,kpa):
        ri=self.maps._idx(ECUMaps.RPM_BINS,rpm);mi=self.maps._idx(ECUMaps.MAP_BINS,kpa)
        for (m,c),w in self._cells.items():w.config(relief='solid' if(m==mi and c==ri) else 'flat')
    def show3d(self):
        if not MPL:return
        try:from mpl_toolkits.mplot3d import Axes3D  # noqa
        except ImportError:messagebox.showinfo('3D','pip install matplotlib');return
        win=tk.Toplevel();win.title(self.title)
        fig=Figure(figsize=(5,4));ax=fig.add_subplot(111,projection='3d')
        tbl=getattr(self.maps,self.attr)
        XX,YY=np.meshgrid(ECUMaps.RPM_BINS,ECUMaps.MAP_BINS)
        ax.plot_surface(XX,YY,np.array(tbl),cmap='jet',edgecolor='none',alpha=0.9)
        ax.set_xlabel('RPM',fontsize=7);ax.set_ylabel('MAP kPa',fontsize=7);ax.set_title(self.title,fontsize=8)
        FigureCanvasTkAgg(fig,master=win).get_tk_widget().pack(fill=tk.BOTH,expand=True)

# --- Fullscreen Scope / Channel Viewer ---
class ScopeWindow(tk.Toplevel):
    NUMERIC_KEYS=["rpm","map_kpa","tps","clt","iat","batt","afr","lam",
                  "pw","dc","dwell","adv","egt","oil","stft","ltft","klvl","spd"]
    def __init__(self,parent,eng,scope,initial_ch1,initial_ch2):
        super().__init__(parent)
        self.eng=eng;self.scope=scope
        self.title("CYBERKNIFE SCOPE")
        self.configure(bg=BG)
        try:self.attributes("-fullscreen",True)
        except:self.geometry("800x600")
        self._ch=[];self._num=[];self._snaps=[];self._run=True
        self._zoom_x=[None,None]
        self._build(initial_ch1,initial_ch2)
        self._tick()
        self.protocol("WM_DELETE_WINDOW",self._close)

    def _build(self,c1,c2):
        top=tk.Frame(self,bg="#050a0f");top.pack(fill=tk.X)
        def btn(t,cmd,fg=WHITE,bg="#0f2040"):
            return tk.Button(top,text=t,command=cmd,bg=bg,fg=fg,
                font=("Courier",FS,"bold"),relief="flat",padx=6,pady=3,cursor="hand2")
        btn("X CLOSE",self._close,fg=RED,bg="#200000").pack(side=tk.RIGHT,padx=3,pady=2)
        btn("SNAPSHOT",self._snapshot,fg=AMBER).pack(side=tk.RIGHT,padx=2,pady=2)
        btn("CLR SNAPS",self._clear_snaps,fg=GRAY).pack(side=tk.RIGHT,padx=2,pady=2)
        btn("ZOOM IN",lambda:self._zoom(0.5),fg=CYAN).pack(side=tk.RIGHT,padx=2,pady=2)
        btn("ZOOM OUT",lambda:self._zoom(2.0),fg=CYAN).pack(side=tk.RIGHT,padx=2,pady=2)
        btn("RESET",self._zoom_reset,fg=YELL).pack(side=tk.RIGHT,padx=2,pady=2)
        tk.Label(top,text=" SCOPE ",bg="#050a0f",fg=GREEN,font=("Courier",FM,"bold")).pack(side=tk.LEFT,padx=6)
        left=tk.Frame(self,bg=PANEL,width=155);left.pack(side=tk.LEFT,fill=tk.Y)
        left.pack_propagate(False)
        tk.Label(left,text="WAVEFORMS",bg=PANEL,fg=CYAN,font=("Courier",FS,"bold")).pack(pady=(4,1),padx=3)
        COLORS=[GREEN,AMBER,CYAN,PURP,YELL,RED,BLUE,WHITE]
        self._ch_vars={}
        for i,sig in enumerate(ScopeGen.SIGS):
            v=tk.BooleanVar(value=False)
            col=COLORS[i%len(COLORS)]
            tk.Checkbutton(left,text=sig[:20],variable=v,bg=PANEL,fg=col,
                selectcolor=DARK,font=("Courier",max(6,FS-1)),anchor="w",pady=1,
                command=self._rebuild_channels).pack(fill=tk.X,padx=3)
            self._ch_vars[sig]=(v,col)
        if c1 in self._ch_vars:self._ch_vars[c1][0].set(True)
        if c2 in self._ch_vars:self._ch_vars[c2][0].set(True)
        tk.Frame(left,bg=GRAY,height=1).pack(fill=tk.X,pady=4)
        tk.Label(left,text="NUMERICS",bg=PANEL,fg=AMBER,font=("Courier",FS,"bold")).pack(pady=(2,1),padx=3)
        self._num_vars={}
        for k in self.NUMERIC_KEYS:
            v=tk.BooleanVar(value=(k in ["rpm","map_kpa","afr","stft","ltft"]))
            tk.Checkbutton(left,text=k,variable=v,bg=PANEL,fg=YELL,
                selectcolor=DARK,font=("Courier",max(6,FS-1)),anchor="w",pady=1,
                command=self._refresh_num_strip).pack(fill=tk.X,padx=3)
            self._num_vars[k]=v
        cf=tk.Frame(left,bg=PANEL);cf.pack(fill=tk.X,padx=3,pady=3)
        tk.Label(cf,text="History pts:",bg=PANEL,fg=GRAY,font=("Courier",FS)).pack()
        self._npts=tk.IntVar(value=200)
        tk.Scale(cf,variable=self._npts,from_=50,to=500,orient=tk.HORIZONTAL,
            bg=PANEL,fg=CYAN,troughcolor=DARK,highlightthickness=0,
            font=("Courier",max(6,FS-1)),sliderlength=12).pack(fill=tk.X)
        right=tk.Frame(self,bg=BG);right.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        self._num_frame=tk.Frame(right,bg="#070c10");self._num_frame.pack(fill=tk.X,padx=3,pady=1)
        self._num_labels={}
        for k in self.NUMERIC_KEYS:
            fr=tk.Frame(self._num_frame,bg="#070c10")
            tk.Label(fr,text=k,bg="#070c10",fg=GRAY,font=("Courier",FS)).pack()
            vv=tk.StringVar(value="--")
            tk.Label(fr,textvariable=vv,bg="#070c10",fg=YELL,font=("Courier",FM,"bold")).pack()
            self._num_labels[k]=(fr,vv)
        self._refresh_num_strip()
        if MPL:
            self._fig=Figure(facecolor="#020608")
            self._cv=FigureCanvasTkAgg(self._fig,master=right)
            self._cv.get_tk_widget().pack(fill=tk.BOTH,expand=True,padx=3,pady=3)
            try:
                tb=NavigationToolbar2Tk(self._cv,right)
                tb.config(bg=DARK);tb.update()
            except:pass
        self._snap_lbl=tk.Label(right,text="No snapshots",bg=BG,fg=DIM,
            font=("Courier",FS),anchor="w")
        self._snap_lbl.pack(fill=tk.X,padx=5,pady=1)
        self._rebuild_channels()

    def _refresh_num_strip(self):
        for k,(fr,_) in self._num_labels.items():
            if self._num_vars[k].get():fr.pack(side=tk.LEFT,padx=4,pady=1)
            else:fr.pack_forget()

    def _rebuild_channels(self):
        COLORS=[GREEN,AMBER,CYAN,PURP]
        self._ch=[(sig,col) for sig,(v,col) in self._ch_vars.items() if v.get()][:4]
        self._refresh_num_strip()

    def _zoom(self,factor):
        s=self.eng.snap();rpm=max(100,s["rpm"])
        span=(self._zoom_x[1]-self._zoom_x[0]) if self._zoom_x[0] is not None else (2*60/rpm*1000)
        mid=(self._zoom_x[0]+self._zoom_x[1])/2 if self._zoom_x[0] is not None else span/2
        half=span*factor/2
        self._zoom_x=[max(0,mid-half),mid+half]

    def _zoom_reset(self):self._zoom_x=[None,None]

    def _snapshot(self):
        if not MPL:return
        s=self.eng.snap()
        for sig,col in self._ch:
            res=self.scope.get(sig,s,300)
            if res:
                t,y,_,_,_=res
                label="[%s] %s @%.0fRPM"%(time.strftime("%H:%M:%S"),sig[:12],s["rpm"])
                self._snaps.append((label,t*1000,y.copy(),col))
        self._snap_lbl.config(text="Snaps: "+" | ".join(s[0] for s in self._snaps[-3:]),fg=AMBER)

    def _clear_snaps(self):self._snaps.clear();self._snap_lbl.config(text="No snapshots",fg=DIM)

    def _tick(self):
        if not self._run:return
        s=self.eng.snap()
        FMT={"rpm":"{:.0f}","map_kpa":"{:.0f}kPa","tps":"{:.1f}%","clt":"{:.0f}C","iat":"{:.0f}C",
             "batt":"{:.2f}V","afr":"{:.2f}","lam":"{:.3f}","pw":"{:.2f}ms","dc":"{:.1f}%",
             "dwell":"{:.2f}ms","adv":"{:.1f}d","egt":"{:.0f}C","oil":"{:.0f}psi",
             "stft":"{:+.1f}%","ltft":"{:+.1f}%","klvl":"{:.2f}","spd":"{:.0f}kh"}
        for k,(_,vv) in self._num_labels.items():
            try:vv.set(FMT.get(k,"{}").format(s.get(k,0)))
            except:vv.set(str(s.get(k,"?")))
        if MPL and self._ch:
            n=max(50,min(500,self._npts.get()))
            self._fig.clear()
            nc=len(self._ch)
            self._fig.subplots_adjust(left=0.09,right=0.97,hspace=0.6,top=0.96,bottom=0.05)
            for i,(sig,col) in enumerate(self._ch):
                ax=self._fig.add_subplot(nc,1,i+1)
                ax.set_facecolor("#020608");ax.grid(True,color="#0a1a0a",lw=0.8)
                ax.tick_params(colors="#334433",labelsize=7)
                res=self.scope.get(sig,s,n)
                if res:
                    t,y,ylabel,ymin,ymax=res;tm=t*1000
                    ax.plot(tm,y,color=col,lw=1.5)
                    ax.set_ylabel(ylabel,fontsize=7,color=col)
                    ax.set_ylim(ymin,ymax)
                    ax.set_title(sig,fontsize=8,color=col,pad=2)
                    if self._zoom_x[0] is not None:ax.set_xlim(self._zoom_x[0],self._zoom_x[1])
                    for lbl,st,sy,sc in self._snaps:
                        if len(st)==len(sy):ax.plot(st,sy,color=sc,lw=0.9,alpha=0.4,linestyle="--")
            self._cv.draw()
        self.after(250,self._tick)

    def _close(self):self._run=False;self.destroy()

# --- Mini-graph helper + CyberKnife main app ---
class MiniGraph(tk.Frame):
    """Small live thumbnail graph that opens ScopeWindow on click."""
    def __init__(self,parent,eng,scope,ch1,ch2,title,height=90):
        super().__init__(parent,bg=DARK,relief="ridge",bd=1)
        self.eng=eng;self.scope=scope;self.ch1=ch1;self.ch2=ch2
        self._win=None
        hdr=tk.Frame(self,bg=DARK);hdr.pack(fill=tk.X)
        tk.Label(hdr,text=title,bg=DARK,fg=CYAN,font=("Courier",FS,"bold"),anchor="w").pack(side=tk.LEFT,padx=4)
        tk.Label(hdr,text="[TAP TO EXPAND]",bg=DARK,fg=DIM,font=("Courier",max(5,FS-2))).pack(side=tk.RIGHT,padx=4)
        if MPL:
            self._fig=Figure(facecolor=DARK,figsize=(2,height/72))
            self._fig.subplots_adjust(left=0.05,right=0.99,top=0.95,bottom=0.08,hspace=0.4)
            self._ax1=self._fig.add_subplot(211);self._ax2=self._fig.add_subplot(212)
            for ax in [self._ax1,self._ax2]:
                ax.set_facecolor(DARK);ax.tick_params(left=False,bottom=False,labelleft=False,labelbottom=False)
                ax.grid(False)
            self._cv=FigureCanvasTkAgg(self._fig,master=self)
            w=self._cv.get_tk_widget();w.pack(fill=tk.BOTH,expand=True)
            w.bind("<Button-1>",self._expand)
        else:
            tk.Label(self,text="(MPL not installed)\npip install matplotlib",bg=DARK,fg=GRAY,
                font=("Courier",FS)).pack(expand=True,pady=8)

    def _expand(self,event=None):
        if self._win and self._win.winfo_exists():
            self._win.lift();return
        self._win=ScopeWindow(self.winfo_toplevel(),self.eng,self.scope,self.ch1,self.ch2)

    def update(self,s):
        if not MPL:return
        for ax,ch,col in [(self._ax1,self.ch1,GREEN),(self._ax2,self.ch2,AMBER)]:
            ax.clear();ax.set_facecolor(DARK)
            ax.tick_params(left=False,bottom=False,labelleft=False,labelbottom=False)
            res=self.scope.get(ch,s,60)
            if res:
                t,y,_,ymin,ymax=res
                ax.plot(t*1000,y,color=col,lw=1.0)
                ax.set_ylim(ymin,ymax)
                ax.set_ylabel(ch[:6],fontsize=6,color=col)
        self._fig.tight_layout(pad=0.1);self._cv.draw()


class CyberKnife(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CYBERKNIFE v3.3")
        try:self.attributes("-fullscreen",True)
        except:pass
        self.configure(bg=BG)
        self.maps=ECUMaps();self.eng=EnginePhysics(self.maps)
        self.j1939=J1939Bus(self.eng);self.obd=OBDHandler(self.eng);self.scope=ScopeGen()
        self._H={k:deque(maxlen=300) for k in ["afr","stft","ltft","egt","rpm","knock"]}
        self._log_rows=[];self._log_on=False
        self._style()
        self._build_statusbar()
        self.nb=ttk.Notebook(self);self.nb.pack(fill=tk.BOTH,expand=True,padx=1,pady=1)
        self._tab_mechanic()
        self._tab_scope()
        self._tab_can()
        self._tab_tuning()
        self._tab_corrections()
        self._tab_sensors()
        self._tab_datalog()
        self._tab_faults()
        self.after(400,self._tick)

    def _style(self):
        s=ttk.Style();s.theme_use("clam")
        s.configure("TNotebook",background=BG)
        s.configure("TNotebook.Tab",background=PANEL,foreground="#aaccff",
            padding=[8,4],font=("Courier",FM,"bold"))
        s.map("TNotebook.Tab",background=[("selected","#0f3460")])
        s.configure("TFrame",background=BG)
        s.configure("TLabelframe",background=PANEL)
        s.configure("TLabelframe.Label",background=PANEL,foreground=GREEN,font=("Courier",FS,"bold"))
        s.configure("Treeview",font=("Courier",FS),rowheight=18,
            background=DARK,foreground=WHITE,fieldbackground=DARK)
        s.configure("Treeview.Heading",font=("Courier",FS,"bold"),background=PANEL,foreground=CYAN)
        s.configure("TCombobox",font=("Courier",FM))
        s.configure("TScrollbar",background=PANEL,troughcolor=DARK)

    def _lf(self,p,t):return ttk.LabelFrame(p,text=" "+t+" ")
    def _btn(self,p,txt,cmd,fg=WHITE,bg="#0f3460"):
        return tk.Button(p,text=txt,command=cmd,bg=bg,fg=fg,
            font=("Courier",FM,"bold"),relief="flat",pady=4,cursor="hand2")
    def _scrollable(self,parent):
        c=tk.Canvas(parent,bg=BG,highlightthickness=0)
        sb=ttk.Scrollbar(parent,orient="vertical",command=c.yview)
        c.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y);c.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        inner=tk.Frame(c,bg=BG);wid=c.create_window((0,0),window=inner,anchor="nw")
        def _cfg(e):c.configure(scrollregion=c.bbox("all"));c.itemconfig(wid,width=c.winfo_width())
        inner.bind("<Configure>",_cfg)
        c.bind("<Configure>",lambda e:c.itemconfig(wid,width=e.width))
        return inner
    def _tv(self,parent,cols,widths,h=12):
        f=tk.Frame(parent,bg=BG);f.pack(fill=tk.BOTH,expand=True,padx=2,pady=2)
        f.grid_rowconfigure(0,weight=1);f.grid_columnconfigure(0,weight=1)
        tv=ttk.Treeview(f,columns=cols,show="headings",height=h)
        for col,w in zip(cols,widths):tv.heading(col,text=col);tv.column(col,width=w,anchor=tk.W)
        ys=ttk.Scrollbar(f,orient=tk.VERTICAL,command=tv.yview)
        xs=ttk.Scrollbar(f,orient=tk.HORIZONTAL,command=tv.xview)
        tv.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        tv.grid(row=0,column=0,sticky="nsew");ys.grid(row=0,column=1,sticky="ns")
        xs.grid(row=1,column=0,sticky="ew")
        return tv

    def _build_statusbar(self):
        sb=tk.Frame(self,bg="#050a0f");sb.pack(fill=tk.X)
        self._sb={}
        rows=[
            [("RPM","rpm",RED,"{:.0f}"),("MAP","map_kpa",BLUE,"{:.0f}kPa"),("TPS","tps",AMBER,"{:.1f}%"),
             ("AFR","afr",CYAN,"{:.2f}"),("LAM","lam",CYAN,"{:.3f}"),("IGN","adv",YELL,"{:.1f}d"),
             ("CLT","clt","#ff6666","{:.0f}C"),("IAT","iat","#4466ff","{:.0f}C"),("BATT","batt",GREEN,"{:.2f}V")],
            [("PW","pw","#ff88aa","{:.2f}ms"),("DC","dc","#ff88aa","{:.1f}%"),("EGT","egt","#ff8844","{:.0f}C"),
             ("OIL","oil","#88ccff","{:.0f}psi"),("KMH","spd",GREEN,"{:.0f}"),("GR","gear",WHITE,"{}"),
             ("DWL","dwell",AMBER,"{:.2f}ms"),("STF","stft",AMBER,"{:+.1f}%"),("LTF","ltft",RED,"{:+.1f}%")],
        ]
        for row_data in rows:
            rf=tk.Frame(sb,bg="#050a0f");rf.pack(fill=tk.X)
            for col,(lbl,key,color,fmt) in enumerate(row_data):
                fr=tk.Frame(rf,bg="#050a0f");fr.grid(row=0,column=col,padx=2,pady=1,sticky="ew")
                rf.grid_columnconfigure(col,weight=1)
                tk.Label(fr,text=lbl,bg="#050a0f",fg=GRAY,font=("Courier",FS,"bold")).pack()
                var=tk.StringVar(value="--")
                tk.Label(fr,textvariable=var,bg="#050a0f",fg=color,
                    font=("Courier",FGG,"bold")).pack()
                self._sb[key]=(var,fmt)
        bot=tk.Frame(sb,bg="#0a0505");bot.pack(fill=tk.X)
        self._dtc_v=tk.StringVar(value="  NO DTCs")
        tk.Label(bot,textvariable=self._dtc_v,bg="#0a0505",fg=RED,
            font=("Courier",FM,"bold"),anchor="w").pack(side=tk.LEFT,padx=5)
        self._sc_v=tk.StringVar(value="WARMUP")
        tk.Label(bot,textvariable=self._sc_v,bg="#0a0505",fg=PURP,
            font=("Courier",FM,"bold")).pack(side=tk.RIGHT,padx=6)

    def _tab_mechanic(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" MECH ")
        inner=self._scrollable(f)
        self._mech_result=tk.StringVar(value="Send a request or enable auto-poll")
        self._ap_var=tk.BooleanVar(value=False);self._lv={}
        obd=self._lf(inner,"OBD-II REQUESTS");obd.pack(fill=tk.X,padx=4,pady=4)
        pids=[(0x0C,"RPM"),(0x0D,"Speed"),(0x05,"CLT"),(0x0F,"IAT"),(0x0B,"MAP"),
              (0x11,"TPS"),(0x0E,"Timing"),(0x04,"Load"),(0x06,"STFT"),(0x07,"LTFT"),
              (0x44,"Lambda"),(0x5C,"OilT")]
        for i,(pid,name) in enumerate(pids):
            r,c=divmod(i,3)
            self._btn(obd,"%02Xh %s"%(pid,name),lambda p=pid:self._obd_req(p),fg=CYAN
                ).grid(row=r,column=c,padx=2,pady=2,sticky="ew",ipadx=2)
        for c in range(3):obd.grid_columnconfigure(c,weight=1)
        dtc=self._lf(inner,"DTC + CONTROLS");dtc.pack(fill=tk.X,padx=4,pady=3)
        ctrl_row=tk.Frame(dtc,bg=PANEL);ctrl_row.pack(fill=tk.X,padx=3,pady=3)
        for txt,mode,pid in [("Active DTCs",0x03,None),("Pending DTCs",0x07,None),
                              ("Clear DTCs",0x04,None),("Read VIN",0x09,0x02)]:
            cmd=lambda m=mode,p=pid:self._obd_raw(m,p)
            self._btn(ctrl_row,txt,cmd,fg=AMBER).pack(side=tk.LEFT,padx=3,pady=2,fill=tk.X,expand=True)
        self._btn(dtc,"Freeze Frame",self._freeze,fg=AMBER).pack(fill=tk.X,padx=3,pady=2)
        tk.Checkbutton(dtc,text="AUTO-POLL (400ms)",variable=self._ap_var,bg=PANEL,fg=CYAN,
            selectcolor=DARK,font=("Courier",FM,"bold"),pady=3,
            command=lambda:setattr(self.obd,"autopoll",self._ap_var.get())).pack(anchor=tk.W,padx=4)
        lv=self._lf(inner,"LIVE VALUES");lv.pack(fill=tk.X,padx=4,pady=3)
        items=[("STFT%","stft",AMBER,"{:+.1f}%"),("LTFT%","ltft",AMBER,"{:+.1f}%"),
               ("KNOCK RET","kret",RED,"{:.1f}d"),("KNOCK LVL","klvl",RED,"{:.2f}"),
               ("EGO LOOP","ego",GREEN,"{}"),("VE%","ve_live",GREEN,"{:.1f}%"),
               ("IGN live","ign_live",YELL,"{:.1f}d"),("AFR tgt","afr_tgt",CYAN,"{:.2f}"),
               ("ACCEL","accel",AMBER,"{}")]
        for i,(lbl,key,color,fmt) in enumerate(items):
            r,c=divmod(i,2)
            tk.Label(lv,text=lbl+":",bg=PANEL,fg=GRAY,font=("Courier",FS),anchor="e",width=11
                ).grid(row=r,column=c*2,sticky="e",padx=2,pady=1)
            var=tk.StringVar(value="---")
            tk.Label(lv,textvariable=var,bg=PANEL,fg=color,font=("Courier",FM,"bold"),
                anchor="w",width=9).grid(row=r,column=c*2+1,sticky="w")
            self._lv[key]=(var,fmt)
        res=self._lf(inner,"RESULT");res.pack(fill=tk.X,padx=4,pady=3)
        tk.Label(res,textvariable=self._mech_result,bg=DARK,fg=CYAN,font=("Courier",FM),
            wraplength=340,justify=tk.LEFT,anchor="nw").pack(fill=tk.X,padx=4,pady=4)
        self._mini_afr=MiniGraph(inner,self.eng,self.scope,"Wideband O2","Narrowband O2",
            "AFR LIVE  (tap=expand)",height=88)
        self._mini_afr.pack(fill=tk.X,padx=4,pady=3)

    def _obd_req(self,pid):self._mech_result.set(self.obd.request(0x01,pid))
    def _obd_raw(self,m,p=None):self._mech_result.set(self.obd.request(m,p) or "OK")
    def _freeze(self):
        s=self.eng.snap()
        lines=["=== FREEZE %s ==="%time.strftime("%H:%M:%S")]
        for k,lbl in [("rpm","RPM"),("map_kpa","MAP kPa"),("tps","TPS%"),("clt","CLT"),
                      ("iat","IAT"),("afr","AFR"),("lam","Lambda"),("adv","IGN Adv"),
                      ("pw","PW ms"),("dc","DC%"),("batt","Battery"),("stft","STFT%"),
                      ("ltft","LTFT%"),("kret","Knock Ret"),("egt","EGT")]:
            v=s.get(k,"?")
            lines.append("  %-12s= %s"%(lbl,round(v,3) if isinstance(v,float) else v))
        if s["active_dtcs"]:lines.append("  DTCs: "+", ".join(c for c,_ in s["active_dtcs"]))
        self._mech_result.set("\n".join(lines))

    def _tab_scope(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" SCOPE ")
        self._ch1=tk.StringVar(value=ScopeGen.SIGS[0])
        self._ch2=tk.StringVar(value=ScopeGen.SIGS[3])
        ctrl=tk.Frame(f,bg=BG);ctrl.pack(fill=tk.X,padx=4,pady=3)
        for ch,var,col in [(1,self._ch1,GREEN),(2,self._ch2,AMBER)]:
            row=tk.Frame(ctrl,bg=PANEL);row.pack(fill=tk.X,pady=2)
            tk.Label(row,text="CH%d:"%ch,bg=PANEL,fg=col,font=("Courier",FM,"bold"),width=4).pack(side=tk.LEFT,padx=4)
            ttk.Combobox(row,textvariable=var,values=ScopeGen.SIGS,
                font=("Courier",FM),state="readonly").pack(side=tk.LEFT,fill=tk.X,expand=True,padx=3,ipady=3)
        self._btn(ctrl,"OPEN FULL SCOPE",self._open_scope,fg=GREEN,bg="#002800"
            ).pack(fill=tk.X,padx=4,pady=4)
        tk.Label(ctrl,text="Mini preview — tap button above for zoom/pan/snapshot/channel select",
            bg=BG,fg=DIM,font=("Courier",FS),wraplength=340).pack(padx=4)
        self._mini_scope=MiniGraph(f,self.eng,self.scope,
            ScopeGen.SIGS[0],ScopeGen.SIGS[3],"SCOPE PREVIEW  (tap button or here to expand)",height=130)
        self._mini_scope.pack(fill=tk.BOTH,expand=True,padx=4,pady=3)
        self._mini_scope.bind("<Button-1>",lambda e:self._open_scope())

    def _open_scope(self):
        ScopeWindow(self,self.eng,self.scope,self._ch1.get(),self._ch2.get())

    def _tab_can(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" CAN ")
        nb2=ttk.Notebook(f);nb2.pack(fill=tk.BOTH,expand=True,padx=2,pady=2)
        info=ttk.Frame(nb2);nb2.add(info,text=" INFO ")
        t=tk.Text(info,height=4,bg=DARK,fg="#aaccff",font=("Courier",FS),relief="flat",wrap="none")
        t.pack(fill=tk.X,padx=4,pady=4)
        t.insert("1.0","29-bit ID: [28..26]=Pri [23..8]=PGN [7..0]=SA\n"
            "EEC1:61444 EEC2:61443 ET1:65262 CCVS:65265 DM1:65226\n"
            "OBD-II: Req 7DF  Resp 7E8  (11-bit)\nRate: J1939=100ms  OBD=400ms")
        t.config(state="disabled")
        jt=ttk.Frame(nb2);nb2.add(jt,text=" J1939 ")
        self._j_tv=self._tv(jt,("Time","CAN ID","PGN","Name","SA","Data","Decoded"),
            [62,100,50,130,50,170,260],12)
        ot=ttk.Frame(nb2);nb2.add(ot,text=" OBD-II ")
        self._obd_tv=self._tv(ot,("Time","ID","Dir","Data","Decoded"),
            [62,52,36,200,380],12)

    def _tab_tuning(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" TUNE ")
        self._connected=False
        top=tk.Frame(f,bg=BG);top.pack(fill=tk.X,padx=4,pady=4)
        conn=self._lf(top,"ECU CONN");conn.pack(side=tk.LEFT,fill=tk.Y,padx=2)
        self._conn_v=tk.StringVar(value="OFFLINE")
        self._conn_l=tk.Label(conn,textvariable=self._conn_v,bg="#1a0000",fg=RED,
            font=("Courier",FM,"bold"),width=10)
        self._conn_l.pack(pady=4,padx=4)
        for txt,cmd,col in [("Connect",self._ecu_conn,GREEN),("Disconnect",self._ecu_disc,GRAY),
                             ("Burn",self._burn,RED),("Revert",self._revert,AMBER),
                             ("CSV",self._export_csv,CYAN)]:
            self._btn(conn,txt,cmd,fg=col).pack(fill=tk.X,padx=3,pady=2)
        op=self._lf(top,"LIVE OP POINT");op.pack(side=tk.LEFT,fill=tk.Y,padx=2)
        self._op={}
        for i,(lbl,key,color,fmt) in enumerate([
            ("RPM","rpm",RED,"{:.0f}"),("MAP","map_kpa",BLUE,"{:.0f}kPa"),
            ("VE%","ve_live",GREEN,"{:.1f}%"),("IGN","ign_live",YELL,"{:.1f}d"),
            ("AFRt","afr_tgt",CYAN,"{:.2f}"),("AFRa","afr",CYAN,"{:.2f}"),
            ("STFT","stft",AMBER,"{:+.1f}%"),("LTFT","ltft",AMBER,"{:+.1f}%"),
            ("PW","pw","#ff88aa","{:.2f}ms"),("DC","dc","#ff88aa","{:.1f}%"),
            ("KRet","kret",RED,"{:.1f}d")]):
            tk.Label(op,text=lbl+":",bg=PANEL,fg=GRAY,font=("Courier",FS),
                anchor="e",width=5).grid(row=i,column=0,sticky="e",padx=2,pady=1)
            var=tk.StringVar(value="---")
            tk.Label(op,textvariable=var,bg=PANEL,fg=color,
                font=("Courier",FM,"bold"),width=9).grid(row=i,column=1,sticky="w")
            self._op[key]=(var,fmt)
        mnb=ttk.Notebook(f);mnb.pack(fill=tk.BOTH,expand=True,padx=2,pady=2)
        self._ve_ed=self._map_tab(mnb," VE (%) ","ve_table","%",20,108)
        self._ig_ed=self._map_tab(mnb," IGN (deg) ","ign_table","d",0,42)
        self._afr_ed=self._map_tab(mnb," AFR target ","afr_table",":1",11,17)

    def _map_tab(self,nb,label,attr,unit,vmin,vmax):
        frm=ttk.Frame(nb);nb.add(frm,text=label)
        outer=tk.Frame(frm,bg=BG);outer.pack(fill=tk.BOTH,expand=True)
        canvas=tk.Canvas(outer,bg=BG,highlightthickness=0)
        hsc=ttk.Scrollbar(outer,orient=tk.HORIZONTAL,command=canvas.xview)
        vsc=ttk.Scrollbar(outer,orient=tk.VERTICAL,command=canvas.yview)
        canvas.configure(xscrollcommand=hsc.set,yscrollcommand=vsc.set)
        hsc.pack(side=tk.BOTTOM,fill=tk.X);vsc.pack(side=tk.RIGHT,fill=tk.Y)
        canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG);canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        ed=MapEditor(inner,self.maps,attr,label.strip(),unit,vmin,vmax);ed.pack(padx=2,pady=2)
        self._btn(frm,"  View 3D Surface  ",ed.show3d,fg=CYAN).pack(pady=3)
        return ed

    def _ecu_conn(self):self._connected=True;self._conn_v.set("ONLINE");self._conn_l.config(bg="#001a00",fg=GREEN)
    def _ecu_disc(self):self._connected=False;self._conn_v.set("OFFLINE");self._conn_l.config(bg="#1a0000",fg=RED)
    def _burn(self):
        if not self._connected:messagebox.showerror("Error","Connect ECU first");return
        messagebox.showinfo("Flash","Maps burned to ECU")
    def _revert(self):messagebox.showinfo("Revert","Backup maps restored")
    def _export_csv(self):
        lines=[]
        for name,attr in [("VE","ve_table"),("IGN","ign_table"),("AFR","afr_table")]:
            lines.append("# "+name);lines.append("MAP/RPM,"+",".join(str(r) for r in ECUMaps.RPM_BINS))
            for mi,row in enumerate(getattr(self.maps,attr)):
                lines.append(str(ECUMaps.MAP_BINS[mi])+","+",".join(str(v) for v in row))
            lines.append("")
        path="/sdcard/Download/ck_maps.csv"
        try:open(path,"w").write("\n".join(lines));messagebox.showinfo("Saved","Saved to "+path)
        except Exception as e:messagebox.showerror("Error",str(e))

    def _tab_corrections(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" CORR ")
        inner=self._scrollable(f)
        def crow(title,xs,ys,color):
            lf=self._lf(inner,title);lf.pack(fill=tk.X,padx=4,pady=3)
            hdr=tk.Frame(lf,bg=PANEL);hdr.pack(padx=3,pady=3)
            for i,x in enumerate(xs):
                tk.Label(hdr,text=str(x),bg=PANEL,fg="#88aacc",
                    font=("Courier",FS),width=5).grid(row=0,column=i+1)
            for i,y in enumerate(ys):
                e=tk.Entry(hdr,width=5,font=("Courier",FS),justify="center",bg=DARK,fg=color)
                e.insert(0,str(y));e.grid(row=1,column=i+1,padx=1,pady=1)
        crow("CLT Fuel Corr (%) — cold=more fuel",self.maps.clt_ax,self.maps.clt_corr,BLUE)
        crow("IAT Fuel Corr (%) — hot=less fuel",self.maps.iat_ax,self.maps.iat_corr,CYAN)
        crow("Injector Dead Time vs Battery (ms)",self.maps.dt_v,self.maps.dt_ms,AMBER)
        crow("Idle RPM Target vs CLT",self.maps.idle_cax,self.maps.idle_rpm,GREEN)
        cf=self._lf(inner,"GLOBAL ECU CONFIG");cf.pack(fill=tk.X,padx=4,pady=4)
        gr=tk.Frame(cf,bg=PANEL);gr.pack(padx=3,pady=3)
        self._cfg={}
        for i,(attr,label) in enumerate([("req_fuel","Req Fuel ms"),("soft_cut","Soft Rev Lim"),
            ("hard_cut","Hard Rev Lim"),("accel_mult","Accel Mult x"),("accel_dur","Accel Dur ms"),
            ("knock_step","Knock Step d"),("knock_max","Knock Max d"),("fuel_psi","Fuel Press psi")]):
            r,c=divmod(i,2)
            tk.Label(gr,text=label,bg=PANEL,fg=GRAY,font=("Courier",FS)).grid(row=r*2,column=c,padx=8,pady=1)
            e=tk.Entry(gr,width=8,font=("Courier",FM),justify="center",bg=DARK,fg=AMBER)
            e.insert(0,str(getattr(self.maps,attr,0)));e.grid(row=r*2+1,column=c,padx=8,pady=2)
            self._cfg[attr]=e
        self._btn(cf,"Apply Config",self._apply_cfg,fg=GREEN).pack(pady=6,padx=16,fill=tk.X)

    def _apply_cfg(self):
        for attr,e in self._cfg.items():
            try:setattr(self.maps,attr,float(e.get()))
            except:pass
        messagebox.showinfo("Config","Applied")

    def _tab_sensors(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" SENS ")
        inner=self._scrollable(f);self._sv={}
        sensors=[("Wideband O2","afr",CYAN,"AEM/Innovate :1"),
                 ("Lambda","lam",CYAN,"stoich=1.000"),
                 ("EGT Ch1","egt","#ff8844","K-type MAX6675"),
                 ("Coolant","clt",BLUE,"NTC 2252ohm C"),
                 ("Inlet Air","iat","#4466ff","IAT correction"),
                 ("Oil Press","oil","#88ccff","0-100psi"),
                 ("Battery","batt",GREEN,"Dead time ref"),
                 ("Inj DC","dc","#ff88aa",">85% = maxed"),
                 ("Inj PW","pw","#ff88aa","ms per cycle"),
                 ("Veh Speed","spd",GREEN,"Hall sensor")]
        tf=tk.Frame(inner,bg=BG);tf.pack(fill=tk.X,padx=4,pady=4)
        for i,(name,key,color,tip) in enumerate(sensors):
            r,c=divmod(i,2)
            fr=tk.Frame(tf,bg=DARK,relief="ridge",bd=1)
            fr.grid(row=r,column=c,padx=3,pady=3,ipadx=6,ipady=4,sticky="nsew")
            tf.grid_columnconfigure(c,weight=1)
            tk.Label(fr,text=name,bg=DARK,fg=GRAY,font=("Courier",FM,"bold")).pack()
            var=tk.StringVar(value="---")
            tk.Label(fr,textvariable=var,bg=DARK,fg=color,
                font=("Courier",FGG,"bold")).pack()
            tk.Label(fr,text=tip,bg=DARK,fg=DIM,font=("Courier",FS),
                wraplength=160).pack()
            self._sv[key]=var
        # mini live graphs for EGT+AFR
        self._mini_sens=MiniGraph(inner,self.eng,self.scope,
            "Wideband O2","Knock Sensor","SENSOR LIVE  (tap=expand)",height=88)
        self._mini_sens.pack(fill=tk.X,padx=4,pady=3)

    def _tab_datalog(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" LOG ")
        ctrl=tk.Frame(f,bg=BG);ctrl.pack(fill=tk.X,padx=4,pady=4)
        self._log_v=tk.StringVar(value="LOGGING: OFF")
        tk.Label(ctrl,textvariable=self._log_v,bg=DARK,fg=RED,
            font=("Courier",FM,"bold"),width=16).pack(side=tk.LEFT,padx=4)
        for txt,cmd,col in [("Start",self._log_start,GREEN),("Stop",self._log_stop,RED),
                             ("Save",self._log_save,AMBER),("Clear",self._log_clear,GRAY)]:
            self._btn(ctrl,txt,cmd,fg=col).pack(side=tk.LEFT,padx=2)
        self._log_tv=self._tv(f,
            ("Time","RPM","MAP","TPS","CLT","IAT","AFR","LAM","IGN",
             "STFT","LTFT","PW","DC","KNOCK","EGT","GR","SCENE"),
            [58,50,48,44,44,44,48,52,44,48,48,48,42,50,48,38,60],18)

    def _log_start(self):self._log_on=True;self._log_v.set("LOGGING: ON")
    def _log_stop(self):self._log_on=False;self._log_v.set("STOPPED (%d rows)"%len(self._log_rows))
    def _log_clear(self):self._log_rows.clear();[self._log_tv.delete(i) for i in self._log_tv.get_children()]
    def _log_save(self):
        if not self._log_rows:messagebox.showinfo("Log","No data");return
        path="/sdcard/Download/ck_datalog.csv"
        hdr="time,rpm,map,tps,clt,iat,afr,lambda,ign,stft,ltft,pw,dc,knock,egt,gear,scene"
        try:
            open(path,"w").write(hdr+"\n"+"\n".join(",".join(str(v) for v in r) for r in self._log_rows))
            messagebox.showinfo("Saved","%d rows\n%s"%(len(self._log_rows),path))
        except Exception as e:messagebox.showerror("Error",str(e))

    def _tab_faults(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=" FAULT ")
        inner=self._scrollable(f)
        tk.Label(inner,text="FAULT INJECTION",bg=BG,fg=RED,
            font=("Courier",FL,"bold")).pack(pady=5)
        tk.Label(inner,text="Check a fault to inject — watch DTCs, AFR, trims respond live",
            bg=BG,fg=GRAY,font=("Courier",FS)).pack(pady=1)
        self._fault_vars={}
        for attr,title,desc,color in [
            ("fault_o2","O2 SENSOR DEAD","Open loop / P0131 / STFT freezes",RED),
            ("fault_map","MAP STUCK 50kPa","Wrong fueling at all loads",AMBER),
            ("fault_clt","CLT SHORTED GND","Reads -40C / 180% correction / P0117",BLUE),
            ("fault_lean","VACUUM LEAK","Unmetered air / LTFT+ / P0171",CYAN),
            ("fault_ign","TIMING -10deg","Bad sensor or stretched chain",YELL),
            ("fault_inj","INJECTOR STUCK OPEN","AFR 10-11 / P0201 / DC=100%",PURP)]:
            fr=tk.Frame(inner,bg=PANEL,relief="ridge",bd=1)
            fr.pack(fill=tk.X,padx=8,pady=3,ipadx=8,ipady=5)
            var=tk.BooleanVar(value=False);self._fault_vars[attr]=var
            tk.Checkbutton(fr,text=title,variable=var,bg=PANEL,fg=color,
                selectcolor=DARK,font=("Courier",FM,"bold"),pady=2,
                command=lambda a=attr,v=var:setattr(self.eng,a,v.get())).pack(anchor=tk.W)
            tk.Label(fr,text=desc,bg=PANEL,fg=DIM,
                font=("Courier",FS),justify=tk.LEFT).pack(anchor=tk.W,padx=10,pady=1)
        mf=self._lf(inner,"MISFIRE CYLINDER");mf.pack(fill=tk.X,padx=8,pady=4)
        mfi=tk.Frame(mf,bg=PANEL);mfi.pack(padx=4,pady=4)
        self._miss_v=tk.IntVar(value=0)
        for cyl,lbl in [(0,"None"),(1,"Cyl 1"),(2,"Cyl 2"),(3,"Cyl 3"),(4,"Cyl 4")]:
            tk.Radiobutton(mfi,text=lbl,variable=self._miss_v,value=cyl,bg=PANEL,fg=RED,
                selectcolor=DARK,font=("Courier",FM,"bold"),pady=4,
                command=lambda:setattr(self.eng,"fault_miss",self._miss_v.get())).pack(side=tk.LEFT,padx=6)
        tk.Label(mf,text="Misfire -> knock noise, rough idle, P030x DTC",
            bg=PANEL,fg=DIM,font=("Courier",FS)).pack(pady=2)
        self._btn(inner,"CLEAR ALL FAULTS",self._clear_faults,fg=RED,bg="#3a0000"
            ).pack(pady=10,padx=20,fill=tk.X)

    def _clear_faults(self):
        for attr,var in self._fault_vars.items():var.set(False);setattr(self.eng,attr,False)
        self._miss_v.set(0);self.eng.fault_miss=0
        messagebox.showinfo("Faults","All faults cleared")

    def _tick(self):
        s=self.eng.snap()
        for k in ["afr","stft","ltft","egt","rpm"]:self._H[k].append(s.get(k,0))
        self._H["knock"].append(s["klvl"])
        for key,(var,fmt) in self._sb.items():
            v=s.get(key,0)
            try:var.set(fmt.format(v))
            except:var.set(str(v))
        dtcs=s["active_dtcs"]
        self._dtc_v.set("  DTCs: "+" | ".join(c for c,_ in dtcs) if dtcs else "  NO DTCs")
        self._sc_v.set(s["scenario"].upper())
        for key,(var,fmt) in self._lv.items():
            v=s.get(key,"?")
            try:var.set(fmt.format(v))
            except:var.set(str(v))
        for i in self._obd_tv.get_children():self._obd_tv.delete(i)
        for m in list(self.obd.msgs)[-20:]:
            ts=time.strftime("%H:%M:%S",time.localtime(m["ts"]))
            self._obd_tv.insert("","end",values=(ts,m["id"],m["dir"],m["data"],m["dec"]))
        for i in self._j_tv.get_children():self._j_tv.delete(i)
        for m in list(self.j1939.msgs)[-25:]:
            ts=time.strftime("%H:%M:%S",time.localtime(m["ts"]))
            self._j_tv.insert("","end",values=(ts,m["cid"],m["pgn"],m["name"],m["sa"],m["data"],m["dec"]))
        if hasattr(self,"_op"):
            for key,(var,fmt) in self._op.items():
                v=s.get(key,0)
                try:var.set(fmt.format(v))
                except:var.set(str(v))
            self._ve_ed.cursor(s["rpm"],s["map_kpa"])
            self._ig_ed.cursor(s["rpm"],s["map_kpa"])
            self._afr_ed.cursor(s["rpm"],s["map_kpa"])
        if hasattr(self,"_sv"):
            for key,var in self._sv.items():
                v=s.get(key,"?")
                try:var.set("%.2f"%v if isinstance(v,float) else str(v))
                except:var.set(str(v))
        if hasattr(self,"_mini_afr"):self._mini_afr.update(s)
        if hasattr(self,"_mini_scope"):self._mini_scope.update(s)
        if hasattr(self,"_mini_sens"):self._mini_sens.update(s)
        if self._log_on:
            row=(time.strftime("%H:%M:%S"),"%.0f"%s["rpm"],"%.0f"%s["map_kpa"],"%.1f"%s["tps"],
                 "%.0f"%s["clt"],"%.0f"%s["iat"],"%.2f"%s["afr"],"%.3f"%s["lam"],
                 "%.1f"%s["adv"],"%+.1f"%s["stft"],"%+.1f"%s["ltft"],"%.2f"%s["pw"],
                 "%.1f"%s["dc"],"%.2f"%s["klvl"],"%.0f"%s["egt"],str(s["gear"]),s["scenario"])
            self._log_rows.append(row)
            self._log_tv.insert("","end",values=row)
            ch=self._log_tv.get_children()
            if len(ch)>500:self._log_tv.delete(ch[0])
            self._log_tv.yview_moveto(1)
        self.after(400,self._tick)


if __name__=="__main__":
    CyberKnife().mainloop()
