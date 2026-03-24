#!/usr/bin/env python3
"""
MECHANIC'S CYBERKNIFE v3.2  Pydroid 3 optimised
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
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import numpy as np
    MPL = True
except Exception:
    MPL = False

BG='#0d1117';PANEL='#161b22';DARK='#0a0e14'
GREEN='#00ff88';AMBER='#ffaa00';RED='#ff4040'
BLUE='#4488ff';CYAN='#00ccff';YELL='#ffff44'
PURP='#cc55ff';WHITE='#ddeeff';GRAY='#445566';DIM='#223344'

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
            self.kret=min(self.kret+m.knock_step,m.knock_max)
            self.klvl=min(1,self.klvl+0.4);self.kcnt+=1
        else:
            self.kret=max(0,self.kret-m.knock_rec*dt*10);self.klvl=max(0,self.klvl-0.05)
        self.adv=max(0,ib-self.kret)
        self.dwell=max(1.5,(3.8*(13.5/max(self.batt,8)))-self.rpm*0.0001)
        lean=1.5 if self.fault_lean else 0
        if self.fault_o2:
            self.afr=afr_tgt+lean+random.gauss(0,0.3);self.ego=False
        elif self.fault_inj:
            self.afr=random.uniform(10.2,11.5);self.ego=False
        else:
            self.afr=max(10,min(20,afr_tgt+lean+random.gauss(0,0.08)))
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
            y=np.array([4.8 if int(ti*rpm/60*60)%60 not in(57,58,59) and int(ti*rpm/60*60*10)%10<5 else 0.2 for ti in t])
            return t,y,'V',-0.5,5.5
        if sig=='Cam Hall':
            y=np.array([4.8 if int(ti*rpm/120)%2==0 else 0.2 for ti in t])
            return t,y,'V',-0.5,5.5
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
        if sig=='CAN High':
            return t,np.array([3.5 if int(ti*500000)%10<4 else 2.5 for ti in t]),'V',2.0,4.0
        if sig=='CAN Low':
            return t,np.array([1.5 if int(ti*500000)%10<4 else 2.5 for ti in t]),'V',1.0,3.0
        if sig=='MAP Sensor':
            return t,np.full(n,1+(s['map_kpa']/100)*3.5)+np.random.normal(0,0.015,n),'V',0,5
        if sig=='Wideband O2':
            v=0.5+(s['lam']-0.7)*2.2
            return t,np.array([v+0.05*math.sin(ti*8)+random.gauss(0,0.01) for ti in t]),'V',0,5
        if sig=='Narrowband O2':
            v=0.85 if s['lam']<1 else 0.15
            return t,np.full(n,v)+np.random.normal(0,0.03,n),'V',-0.1,1.1
        if sig=='TPS':
            return t,np.full(n,0.5+(s['tps']/100)*4.0)+np.random.normal(0,0.01,n),'V',0,5
        if sig=='Battery/Alt':
            ripple=0.12*np.sin(t*120*2*math.pi) if rpm>900 else np.zeros(n)
            return t,np.full(n,batt)+ripple+np.random.normal(0,0.02,n),'V',10,15.5
        if sig=='Injector DC':
            cy=60/rpm
            return t,np.array([12 if (ti%cy)/cy<(dc/100) else 0 for ti in t]),'V',-1,14
        if sig=='Knock Sensor':
            y=np.random.normal(0,0.05+klvl*0.8,n)
            if klvl>0.3:
                for k in range(0,n,n//4):
                    b=min(8,n-k);y[k:k+b]+=np.sin(np.linspace(0,4*math.pi,b))*(klvl*1.5)
            return t,y,'V',-2,2
        if sig=='Fuel Pump PWM':
            return t,np.array([12 if (ti*80)%1<0.65 else 0 for ti in t]),'V',-1,14
        return None


class MapEditor(tk.Frame):
    def __init__(self,parent,maps,attr,title,unit,vmin,vmax):
        super().__init__(parent,bg=PANEL)
        self.maps=maps;self.attr=attr;self.title=title
        self.unit=unit;self.vmin=vmin;self.vmax=vmax;self._cells={}
        self._build()
    def _build(self):
        tbl=getattr(self.maps,self.attr)
        tk.Label(self,text='kPa|RPM',bg=PANEL,fg=GRAY,font=('Courier',7)).grid(row=0,column=0,padx=1)
        for ci,rpm in enumerate(ECUMaps.RPM_BINS):
            tk.Label(self,text=str(rpm),bg=PANEL,fg='#88aacc',font=('Courier',8)).grid(row=0,column=ci+1,padx=1)
        for mi,kpa in enumerate(ECUMaps.MAP_BINS):
            tk.Label(self,text=str(kpa),bg=PANEL,fg='#88aacc',font=('Courier',8)).grid(row=mi+1,column=0,padx=2)
            for ci in range(len(ECUMaps.RPM_BINS)):
                v=tbl[mi][ci]
                e=tk.Entry(self,width=5,font=('Courier',8),justify='center',bg=self._col(v),fg=WHITE,relief='flat',bd=1)
                e.insert(0,str(v));e.grid(row=mi+1,column=ci+1,padx=1,pady=1)
                e.bind('<FocusOut>',lambda ev,m=mi,c=ci:self._save(m,c,ev.widget))
                self._cells[(mi,ci)]=e
    def _save(self,mi,ci,w):
        try:
            v=float(w.get());getattr(self.maps,self.attr)[mi][ci]=round(v,1);w.config(bg=self._col(v))
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
        ax.set_xlabel('RPM',fontsize=8);ax.set_ylabel('MAP kPa',fontsize=8);ax.set_title(self.title,fontsize=9)
        FigureCanvasTkAgg(fig,master=win).get_tk_widget().pack(fill=tk.BOTH,expand=True)

class CyberKnife(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('CYBERKNIFE v3.2')
        try:self.attributes('-fullscreen',True)
        except:pass
        self.configure(bg=BG)
        self.maps=ECUMaps();self.eng=EnginePhysics(self.maps)
        self.j1939=J1939Bus(self.eng);self.obd=OBDHandler(self.eng);self.scope=ScopeGen()
        self._H={k:deque(maxlen=200) for k in ['afr','stft','ltft','egt','rpm','knock']}
        self._log_rows=[];self._log_on=False
        self.update_idletasks()
        h=max(600,self.winfo_screenheight());w=max(360,self.winfo_screenwidth())
        self._fs=max(9,h//80);self._fm=max(11,h//65);self._fl=max(13,h//52);self._fg=max(15,h//44);self._sw=w
        self._style();self._build_statusbar()
        self.nb=ttk.Notebook(self);self.nb.pack(fill=tk.BOTH,expand=True,padx=2,pady=2)
        self._tab_mechanic();self._tab_scope();self._tab_can()
        self._tab_tuning();self._tab_corrections();self._tab_sensors()
        self._tab_datalog();self._tab_faults()
        self.after(500,self._tick)

    def _style(self):
        s=ttk.Style();s.theme_use('clam')
        px=max(10,self._sw//55);py=max(5,self.winfo_screenheight()//110);rh=max(24,self.winfo_screenheight()//38)
        s.configure('TNotebook',background=BG)
        s.configure('TNotebook.Tab',background=PANEL,foreground='#aaccff',padding=[px,py],font=('Courier',self._fl,'bold'))
        s.map('TNotebook.Tab',background=[('selected','#0f3460')])
        s.configure('TFrame',background=BG);s.configure('TLabelframe',background=PANEL)
        s.configure('TLabelframe.Label',background=PANEL,foreground=GREEN,font=('Courier',self._fs,'bold'))
        s.configure('Treeview',font=('Courier',self._fs),rowheight=rh,background=DARK,foreground=WHITE,fieldbackground=DARK)
        s.configure('Treeview.Heading',font=('Courier',self._fs,'bold'),background=PANEL,foreground=CYAN)
        s.configure('TCombobox',font=('Courier',self._fm));s.configure('TScrollbar',background=PANEL,troughcolor=DARK)

    def _lf(self,p,t):return ttk.LabelFrame(p,text=' '+t+' ')
    def _btn(self,p,txt,cmd,fg=WHITE,bg='#0f3460'):
        return tk.Button(p,text=txt,command=cmd,bg=bg,fg=fg,font=('Courier',self._fl,'bold'),relief='flat',pady=6,cursor='hand2')
    def _scrollable(self,parent):
        c=tk.Canvas(parent,bg=BG,highlightthickness=0);sb=ttk.Scrollbar(parent,orient='vertical',command=c.yview)
        c.configure(yscrollcommand=sb.set);sb.pack(side=tk.RIGHT,fill=tk.Y);c.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        inner=tk.Frame(c,bg=BG);wid=c.create_window((0,0),window=inner,anchor='nw')
        def _cfg(e):c.configure(scrollregion=c.bbox('all'));c.itemconfig(wid,width=c.winfo_width())
        inner.bind('<Configure>',_cfg);c.bind('<Configure>',lambda e:c.itemconfig(wid,width=e.width))
        return inner
    def _tv(self,parent,cols,widths,h=14):
        f=tk.Frame(parent,bg=BG);f.pack(fill=tk.BOTH,expand=True,padx=4,pady=4)
        f.grid_rowconfigure(0,weight=1);f.grid_columnconfigure(0,weight=1)
        tv=ttk.Treeview(f,columns=cols,show='headings',height=h)
        for col,w in zip(cols,widths):tv.heading(col,text=col);tv.column(col,width=w,anchor=tk.W)
        ys=ttk.Scrollbar(f,orient=tk.VERTICAL,command=tv.yview)
        xs=ttk.Scrollbar(f,orient=tk.HORIZONTAL,command=tv.xview)
        tv.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        tv.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew')
        return tv
    def _graph(self,parent,nrows,title=''):
        if not MPL:return None,[],None
        outer=self._lf(parent,title) if title else tk.Frame(parent,bg=BG)
        outer.pack(fill=tk.BOTH,expand=True,padx=4,pady=4)
        fig=Figure(facecolor=DARK)
        fig.subplots_adjust(left=0.10,right=0.97,hspace=0.52,top=0.93,bottom=0.10)
        axes=[fig.add_subplot(nrows,1,i+1) for i in range(nrows)]
        for ax in axes:ax.set_facecolor(DARK);ax.grid(True,color='#1a2535',lw=0.5);ax.tick_params(colors=GRAY,labelsize=8)
        cv=FigureCanvasTkAgg(fig,master=outer);cv.get_tk_widget().pack(fill=tk.BOTH,expand=True)
        return fig,axes,cv

    def _build_statusbar(self):
        sb=tk.Frame(self,bg='#050a0f');sb.pack(fill=tk.X)
        self._sb={}
        rows=[
            [('RPM','rpm',RED,'{:.0f}'),('MAP','map_kpa',BLUE,'{:.0f}kPa'),('TPS','tps',AMBER,'{:.1f}%'),('AFR','afr',CYAN,'{:.2f}'),('LAM','lam',CYAN,'{:.3f}'),('IGN','adv',YELL,'{:.1f}')],
            [('CLT','clt','#ff6666','{:.0f}C'),('IAT','iat','#4466ff','{:.0f}C'),('PW','pw','#ff88aa','{:.2f}ms'),('DC','dc','#ff88aa','{:.1f}%'),('EGT','egt','#ff8844','{:.0f}C'),('OIL','oil','#88ccff','{:.0f}psi')],
            [('BAT','batt',GREEN,'{:.2f}V'),('KMH','spd',GREEN,'{:.0f}'),('GR','gear',WHITE,'{}'),('DWL','dwell',AMBER,'{:.2f}ms'),('STF','stft',AMBER,'{:+.1f}%'),('LTF','ltft',RED,'{:+.1f}%')],
        ]
        for row_data in rows:
            rf=tk.Frame(sb,bg='#050a0f');rf.pack(fill=tk.X)
            for col,(lbl,key,color,fmt) in enumerate(row_data):
                fr=tk.Frame(rf,bg='#050a0f');fr.grid(row=0,column=col,padx=3,pady=1,sticky='ew')
                rf.grid_columnconfigure(col,weight=1)
                tk.Label(fr,text=lbl,bg='#050a0f',fg=GRAY,font=('Courier',self._fs,'bold')).pack()
                var=tk.StringVar(value='--')
                tk.Label(fr,textvariable=var,bg='#050a0f',fg=color,font=('Courier',self._fg,'bold')).pack()
                self._sb[key]=(var,fmt)
        bot=tk.Frame(sb,bg='#0a0505');bot.pack(fill=tk.X)
        self._dtc_v=tk.StringVar(value='  NO DTCs')
        tk.Label(bot,textvariable=self._dtc_v,bg='#0a0505',fg=RED,font=('Courier',self._fm,'bold'),anchor='w').pack(side=tk.LEFT,padx=6)
        self._sc_v=tk.StringVar(value='WARMUP')
        tk.Label(bot,textvariable=self._sc_v,bg='#0a0505',fg=PURP,font=('Courier',self._fm,'bold')).pack(side=tk.RIGHT,padx=8)

    def _tab_mechanic(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' MECH ')
        inner=self._scrollable(f)
        self._mech_result=tk.StringVar(value='Send a request or enable auto-poll')
        self._ap_var=tk.BooleanVar(value=False);self._lv={}
        obd=self._lf(inner,'OBD-II REQUESTS');obd.pack(fill=tk.X,padx=6,pady=6)
        pids=[(0x0C,'RPM'),(0x0D,'Speed'),(0x05,'CLT'),(0x0F,'IAT'),(0x0B,'MAP'),(0x11,'TPS'),(0x0E,'Timing'),(0x04,'Load'),(0x06,'STFT'),(0x07,'LTFT'),(0x44,'Lambda'),(0x5C,'OilT')]
        for i,(pid,name) in enumerate(pids):
            r,c=divmod(i,2)
            self._btn(obd,'%02Xh %s'%(pid,name),lambda p=pid:self._obd_req(p),fg=CYAN).grid(row=r,column=c,padx=4,pady=4,sticky='ew',ipadx=4)
        obd.grid_columnconfigure(0,weight=1);obd.grid_columnconfigure(1,weight=1)
        dtc=self._lf(inner,'DTC + CONTROLS');dtc.pack(fill=tk.X,padx=6,pady=4)
        for txt,mode,pid in [('Active DTCs',0x03,None),('Pending DTCs',0x07,None),('Clear DTCs',0x04,None),('Read VIN',0x09,0x02),('Freeze Frame',None,None)]:
            cmd=(lambda m=mode,p=pid:self._obd_raw(m,p)) if mode else self._freeze
            self._btn(dtc,txt,cmd,fg=AMBER).pack(fill=tk.X,padx=6,pady=3)
        tk.Checkbutton(dtc,text='AUTO-POLL',variable=self._ap_var,bg=PANEL,fg=CYAN,selectcolor=DARK,font=('Courier',self._fl,'bold'),pady=6,command=lambda:setattr(self.obd,'autopoll',self._ap_var.get())).pack(anchor=tk.W,padx=6,pady=4)
        lv=self._lf(inner,'LIVE VALUES');lv.pack(fill=tk.X,padx=6,pady=4)
        for i,(lbl,key,color,fmt) in enumerate([('STFT%','stft',AMBER,'{:+.1f}%'),('LTFT%','ltft',AMBER,'{:+.1f}%'),('KNOCK RET','kret',RED,'{:.1f}deg'),('KNOCK LVL','klvl',RED,'{:.2f}'),('EGO','ego',GREEN,'{}'),('VE%','ve_live',GREEN,'{:.1f}%'),('IGN live','ign_live',YELL,'{:.1f}deg'),('AFR tgt','afr_tgt',CYAN,'{:.2f}'),('ACCEL','accel',AMBER,'{}')]):
            tk.Label(lv,text=lbl+':',bg=PANEL,fg=GRAY,font=('Courier',self._fs),anchor='e',width=12).grid(row=i,column=0,sticky='e',padx=4,pady=3)
            var=tk.StringVar(value='---')
            tk.Label(lv,textvariable=var,bg=PANEL,fg=color,font=('Courier',self._fm,'bold'),anchor='w',width=10).grid(row=i,column=1,sticky='w')
            self._lv[key]=(var,fmt)
        res=self._lf(inner,'RESULT');res.pack(fill=tk.X,padx=6,pady=4)
        tk.Label(res,textvariable=self._mech_result,bg=DARK,fg=CYAN,font=('Courier',self._fm),wraplength=max(200,self._sw-60),justify=tk.LEFT,anchor='nw').pack(fill=tk.X,padx=6,pady=6)
        fig,axes,cv=self._graph(inner,2,'AFR + Fuel Trims')
        if axes:self._mfig=fig;self._max1=axes[0];self._max2=axes[1];self._mcv=cv

    def _obd_req(self,pid):self._mech_result.set(self.obd.request(0x01,pid))
    def _obd_raw(self,m,p=None):self._mech_result.set(self.obd.request(m,p) or 'OK')
    def _freeze(self):
        s=self.eng.snap()
        lines=['=== FREEZE %s ==='%time.strftime('%H:%M:%S')]
        for k,lbl in [('rpm','RPM'),('map_kpa','MAP kPa'),('tps','TPS%'),('clt','CLT'),('iat','IAT'),('afr','AFR'),('lam','Lambda'),('adv','IGN Adv'),('pw','PW ms'),('dc','DC%'),('batt','Battery'),('stft','STFT%'),('ltft','LTFT%'),('kret','Knock Ret'),('egt','EGT')]:
            v=s.get(k,'?');lines.append('  %-12s= %s'%(lbl,round(v,3) if isinstance(v,float) else v))
        if s['active_dtcs']:lines.append('  DTCs: '+', '.join(c for c,_ in s['active_dtcs']))
        self._mech_result.set('\n'.join(lines))

    def _tab_scope(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' SCOPE ')
        self._ch1=tk.StringVar(value=ScopeGen.SIGS[0]);self._ch2=tk.StringVar(value=ScopeGen.SIGS[3])
        self._ch1_en=tk.BooleanVar(value=True);self._ch2_en=tk.BooleanVar(value=True)
        self._sinfo=tk.StringVar(value='')
        ctrl=tk.Frame(f,bg=BG);ctrl.pack(fill=tk.X,padx=6,pady=6)
        for ch,var,en,col in [(1,self._ch1,self._ch1_en,GREEN),(2,self._ch2,self._ch2_en,AMBER)]:
            row=tk.Frame(ctrl,bg=PANEL);row.pack(fill=tk.X,pady=4)
            tk.Checkbutton(row,text='CH%d'%ch,variable=en,bg=PANEL,fg=col,selectcolor=DARK,font=('Courier',self._fl,'bold')).pack(side=tk.LEFT,padx=8)
            ttk.Combobox(row,textvariable=var,values=ScopeGen.SIGS,font=('Courier',self._fm),state='readonly').pack(side=tk.LEFT,fill=tk.X,expand=True,padx=6,ipady=5)
        tk.Label(ctrl,textvariable=self._sinfo,bg=BG,fg=CYAN,font=('Courier',self._fm)).pack(anchor=tk.W,padx=8,pady=4)
        if MPL:
            gf=tk.Frame(f,bg=BG);gf.pack(fill=tk.BOTH,expand=True,padx=4,pady=4)
            self._sfig=Figure(facecolor='#030810')
            self._sfig.subplots_adjust(left=0.09,right=0.97,hspace=0.42,top=0.95,bottom=0.08)
            self._sax1=self._sfig.add_subplot(211);self._sax2=self._sfig.add_subplot(212)
            for ax in [self._sax1,self._sax2]:ax.set_facecolor('#030810');ax.grid(True,color='#081508',lw=0.9);ax.tick_params(colors=DIM,labelsize=9)
            self._scv=FigureCanvasTkAgg(self._sfig,master=gf);self._scv.get_tk_widget().pack(fill=tk.BOTH,expand=True)

    def _tab_can(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' CAN ')
        nb2=ttk.Notebook(f);nb2.pack(fill=tk.BOTH,expand=True,padx=4,pady=4)
        info=ttk.Frame(nb2);nb2.add(info,text=' INFO ')
        t=tk.Text(info,height=5,bg=DARK,fg='#aaccff',font=('Courier',self._fs),relief='flat',wrap='none')
        t.pack(fill=tk.X,padx=6,pady=6)
        t.insert('1.0','29-bit CAN ID: [28..26]=Priority  [23..8]=PGN  [7..0]=SA\nEEC1: Pri=3 PGN=61444(0xF004) SA=0x00 -> 0x0CF00400\nEEC2:61443  ET1:65262  CCVS:65265  DM1:65226\nOBD-II: Request 7DF  Response 7E8  (11-bit ID)')
        t.config(state='disabled')
        jt=ttk.Frame(nb2);nb2.add(jt,text=' J1939 ')
        self._j_tv=self._tv(jt,('Time','CAN ID','PGN','Name','SA','Data','Decoded'),[68,110,55,140,56,190,280],14)
        ot=ttk.Frame(nb2);nb2.add(ot,text=' OBD-II ')
        self._obd_tv=self._tv(ot,('Time','ID','Dir','Data','Decoded'),[68,58,38,210,420],14)

    def _tab_tuning(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' TUNE ')
        self._connected=False
        top=tk.Frame(f,bg=BG);top.pack(fill=tk.X,padx=6,pady=6)
        conn=self._lf(top,'ECU CONNECTION');conn.pack(side=tk.LEFT,fill=tk.Y,padx=4)
        self._conn_v=tk.StringVar(value='DISCONNECTED')
        self._conn_l=tk.Label(conn,textvariable=self._conn_v,bg='#1a0000',fg=RED,font=('Courier',self._fl,'bold'),width=13)
        self._conn_l.pack(pady=6,padx=6)
        for txt,cmd,col in [('Connect',self._ecu_conn,GREEN),('Disconnect',self._ecu_disc,GRAY),('Burn Flash',self._burn,RED),('Revert',self._revert,AMBER),('Export CSV',self._export_csv,CYAN)]:
            self._btn(conn,txt,cmd,fg=col).pack(fill=tk.X,padx=6,pady=3)
        op=self._lf(top,'LIVE OP POINT');op.pack(side=tk.LEFT,fill=tk.Y,padx=4)
        self._op={}
        for i,(lbl,key,color,fmt) in enumerate([('RPM','rpm',RED,'{:.0f}'),('MAP kPa','map_kpa',BLUE,'{:.0f}'),('VE%','ve_live',GREEN,'{:.1f}%'),('IGN Adv','ign_live',YELL,'{:.1f}deg'),('AFR tgt','afr_tgt',CYAN,'{:.2f}'),('AFR act','afr',CYAN,'{:.2f}'),('STFT%','stft',AMBER,'{:+.1f}%'),('LTFT%','ltft',AMBER,'{:+.1f}%'),('PW ms','pw','#ff88aa','{:.2f}'),('DC%','dc','#ff88aa','{:.1f}'),('Knock Ret','kret',RED,'{:.1f}deg')]):
            tk.Label(op,text=lbl+':',bg=PANEL,fg=GRAY,font=('Courier',self._fs),anchor='e',width=10).grid(row=i,column=0,sticky='e',padx=3,pady=2)
            var=tk.StringVar(value='---')
            tk.Label(op,textvariable=var,bg=PANEL,fg=color,font=('Courier',self._fm,'bold'),width=10).grid(row=i,column=1,sticky='w')
            self._op[key]=(var,fmt)
        mnb=ttk.Notebook(f);mnb.pack(fill=tk.BOTH,expand=True,padx=4,pady=4)
        self._ve_ed=self._map_tab(mnb,' VE Table (%) ','ve_table','%',20,108)
        self._ig_ed=self._map_tab(mnb,' IGN Adv (deg) ','ign_table','deg',0,42)
        self._afr_ed=self._map_tab(mnb,' AFR Target ','afr_table',':1',11,17)

    def _map_tab(self,nb,label,attr,unit,vmin,vmax):
        frm=ttk.Frame(nb);nb.add(frm,text=label)
        outer=tk.Frame(frm,bg=BG);outer.pack(fill=tk.BOTH,expand=True)
        canvas=tk.Canvas(outer,bg=BG,highlightthickness=0)
        hsc=ttk.Scrollbar(outer,orient=tk.HORIZONTAL,command=canvas.xview)
        vsc=ttk.Scrollbar(outer,orient=tk.VERTICAL,command=canvas.yview)
        canvas.configure(xscrollcommand=hsc.set,yscrollcommand=vsc.set)
        hsc.pack(side=tk.BOTTOM,fill=tk.X);vsc.pack(side=tk.RIGHT,fill=tk.Y)
        canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        inner=tk.Frame(canvas,bg=BG);canvas.create_window((0,0),window=inner,anchor='nw')
        inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        ed=MapEditor(inner,self.maps,attr,label.strip(),unit,vmin,vmax);ed.pack(padx=4,pady=4)
        self._btn(frm,'  View 3D Surface  ',ed.show3d,fg=CYAN).pack(pady=4)
        return ed

    def _ecu_conn(self):self._connected=True;self._conn_v.set('CONNECTED');self._conn_l.config(bg='#001a00',fg=GREEN)
    def _ecu_disc(self):self._connected=False;self._conn_v.set('DISCONNECTED');self._conn_l.config(bg='#1a0000',fg=RED)
    def _burn(self):
        if not self._connected:messagebox.showerror('Error','Connect ECU first');return
        messagebox.showinfo('Flash','Maps burned')
    def _revert(self):messagebox.showinfo('Revert','Backup maps restored')
    def _export_csv(self):
        lines=[]
        for name,attr in [('VE','ve_table'),('IGN','ign_table'),('AFR','afr_table')]:
            lines.append('# '+name);lines.append('MAP/RPM,'+','.join(str(r) for r in ECUMaps.RPM_BINS))
            for mi,row in enumerate(getattr(self.maps,attr)):lines.append(str(ECUMaps.MAP_BINS[mi])+','+','.join(str(v) for v in row))
            lines.append('')
        path='/sdcard/Download/ck_maps.csv'
        try:open(path,'w').write('\n'.join(lines));messagebox.showinfo('Saved','Saved to '+path)
        except Exception as e:messagebox.showerror('Error',str(e))

    def _tab_corrections(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' CORR ')
        inner=self._scrollable(f)
        def crow(title,xs,ys,color):
            lf=self._lf(inner,title);lf.pack(fill=tk.X,padx=6,pady=4)
            hdr=tk.Frame(lf,bg=PANEL);hdr.pack(padx=4,pady=4)
            for i,x in enumerate(xs):tk.Label(hdr,text=str(x),bg=PANEL,fg='#88aacc',font=('Courier',self._fs),width=5).grid(row=0,column=i+1)
            for i,y in enumerate(ys):
                e=tk.Entry(hdr,width=5,font=('Courier',self._fs),justify='center',bg=DARK,fg=color)
                e.insert(0,str(y));e.grid(row=1,column=i+1,padx=1,pady=2)
        crow('CLT Fuel Correction (%)  100=no change',self.maps.clt_ax,self.maps.clt_corr,BLUE)
        crow('IAT Fuel Correction (%)  hot=less fuel',self.maps.iat_ax,self.maps.iat_corr,CYAN)
        crow('Injector Dead Time vs Battery (ms)',self.maps.dt_v,self.maps.dt_ms,AMBER)
        crow('Idle RPM Target vs CLT',self.maps.idle_cax,self.maps.idle_rpm,GREEN)
        cf=self._lf(inner,'GLOBAL ECU CONFIG');cf.pack(fill=tk.X,padx=6,pady=6)
        gr=tk.Frame(cf,bg=PANEL);gr.pack(padx=4,pady=4)
        self._cfg={}
        for i,(attr,label) in enumerate([('req_fuel','Req Fuel ms'),('soft_cut','Soft Rev Limit'),('hard_cut','Hard Rev Limit'),('accel_mult','Accel Mult x'),('accel_dur','Accel Dur ms'),('knock_step','Knock Step deg'),('knock_max','Knock Max deg'),('fuel_psi','Fuel Press psi')]):
            r,c=divmod(i,2)
            tk.Label(gr,text=label,bg=PANEL,fg=GRAY,font=('Courier',self._fs)).grid(row=r*2,column=c,padx=10,pady=1)
            e=tk.Entry(gr,width=8,font=('Courier',self._fm),justify='center',bg=DARK,fg=AMBER)
            e.insert(0,str(getattr(self.maps,attr,0)));e.grid(row=r*2+1,column=c,padx=10,pady=3);self._cfg[attr]=e
        self._btn(cf,'Apply Config',self._apply_cfg,fg=GREEN).pack(pady=8,padx=20,fill=tk.X)

    def _apply_cfg(self):
        for attr,e in self._cfg.items():
            try:setattr(self.maps,attr,float(e.get()))
            except:pass
        messagebox.showinfo('Config','Applied')

    def _tab_sensors(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' SENS ')
        inner=self._scrollable(f);self._sv={}
        sensors=[('Wideband O2','afr',CYAN,'AEM/Innovate AFR :1'),('Lambda','lam',CYAN,'1.000=stoich 0.85=WOT rich'),('EGT Ch1','egt','#ff8844','K-type MAX6675 deg C'),('Coolant','clt',BLUE,'NTC 2252ohm deg C'),('Inlet Air','iat','#4466ff','IAT correction table'),('Oil Pressure','oil','#88ccff','0-100psi piezo psi'),('Battery','batt',GREEN,'Dead time table V'),('Inj DC','dc','#ff88aa','Above 85% near maxed %'),('Inj PW','pw','#ff88aa','ms per cycle'),('Veh Speed','spd',GREEN,'Hall sensor km/h')]
        tf=tk.Frame(inner,bg=BG);tf.pack(fill=tk.X,padx=6,pady=6)
        for i,(name,key,color,tip) in enumerate(sensors):
            r,c=divmod(i,2)
            fr=tk.Frame(tf,bg=DARK,relief='ridge',bd=2)
            fr.grid(row=r,column=c,padx=5,pady=5,ipadx=8,ipady=6,sticky='nsew')
            tf.grid_columnconfigure(c,weight=1)
            tk.Label(fr,text=name,bg=DARK,fg=GRAY,font=('Courier',self._fm,'bold')).pack()
            var=tk.StringVar(value='---')
            tk.Label(fr,textvariable=var,bg=DARK,fg=color,font=('Courier',self._fg,'bold')).pack()
            tk.Label(fr,text=tip,bg=DARK,fg=DIM,font=('Courier',max(7,self._fs-1)),wraplength=max(140,self._sw//2-40)).pack()
            self._sv[key]=var
        fig,axes,cv=self._graph(inner,3,'Fuel Trims / EGT / AFR History')
        if axes:self._tfig=fig;self._tax=axes;self._tcv=cv

    def _tab_datalog(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' LOG ')
        ctrl=tk.Frame(f,bg=BG);ctrl.pack(fill=tk.X,padx=6,pady=6)
        self._log_v=tk.StringVar(value='LOGGING: OFF')
        tk.Label(ctrl,textvariable=self._log_v,bg=DARK,fg=RED,font=('Courier',self._fl,'bold'),width=18).pack(side=tk.LEFT,padx=6)
        for txt,cmd,col in [('Start',self._log_start,GREEN),('Stop',self._log_stop,RED),('Save CSV',self._log_save,AMBER),('Clear',self._log_clear,GRAY)]:
            self._btn(ctrl,txt,cmd,fg=col).pack(side=tk.LEFT,padx=4)
        self._log_tv=self._tv(f,('Time','RPM','MAP','TPS','CLT','IAT','AFR','LAM','IGN','STFT','LTFT','PW','DC','KNOCK','EGT','GEAR','SCENE'),[64,58,52,48,48,48,52,56,48,52,52,52,48,54,52,42,70],20)

    def _log_start(self):self._log_on=True;self._log_v.set('LOGGING: ON  o')
    def _log_stop(self):self._log_on=False;self._log_v.set('STOPPED (%d rows)'%len(self._log_rows))
    def _log_clear(self):self._log_rows.clear();[self._log_tv.delete(i) for i in self._log_tv.get_children()]
    def _log_save(self):
        if not self._log_rows:messagebox.showinfo('Log','No data');return
        path='/sdcard/Download/ck_datalog.csv'
        hdr='time,rpm,map,tps,clt,iat,afr,lambda,ign,stft,ltft,pw,dc,knock,egt,gear,scene'
        try:
            open(path,'w').write(hdr+'\n'+'\n'.join(','.join(str(v) for v in r) for r in self._log_rows))
            messagebox.showinfo('Saved','%d rows\n%s'%(len(self._log_rows),path))
        except Exception as e:messagebox.showerror('Error',str(e))

    def _tab_faults(self):
        f=ttk.Frame(self.nb);self.nb.add(f,text=' FAULT ')
        inner=self._scrollable(f)
        tk.Label(inner,text='FAULT INJECTION',bg=BG,fg=RED,font=('Courier',self._fl,'bold')).pack(pady=8)
        tk.Label(inner,text='Tick a fault  watch DTC strip, AFR and trims respond live',bg=BG,fg=GRAY,font=('Courier',self._fs)).pack(pady=2)
        self._fault_vars={}
        for attr,title,desc,color in [
            ('fault_o2','O2 SENSOR DEAD','ECU goes open-loop\nP0131 sets  STFT/LTFT stop learning',RED),
            ('fault_map','MAP STUCK 50kPa','Wrong fueling all loads\nAFR swings rich/lean',AMBER),
            ('fault_clt','CLT SHORTED GND','Reads -40C constantly\n180% cold fuel correction\nP0117',BLUE),
            ('fault_lean','VACUUM LEAK','Unmetered air added\nLTFT goes positive\nP0171 if severe',CYAN),
            ('fault_ign','TIMING -10deg','Bad knock sensor / worn chain\nPower loss',YELL),
            ('fault_inj','INJECTOR STUCK OPEN','AFR 10-11:1 very rich\nP0201 sets  DC=100%',PURP)]:
            fr=tk.Frame(inner,bg=PANEL,relief='ridge',bd=2)
            fr.pack(fill=tk.X,padx=12,pady=6,ipadx=10,ipady=8)
            var=tk.BooleanVar(value=False);self._fault_vars[attr]=var
            tk.Checkbutton(fr,text=title,variable=var,bg=PANEL,fg=color,selectcolor=DARK,font=('Courier',self._fl,'bold'),pady=4,command=lambda a=attr,v=var:setattr(self.eng,a,v.get())).pack(anchor=tk.W)
            tk.Label(fr,text=desc,bg=PANEL,fg=DIM,font=('Courier',self._fs),justify=tk.LEFT).pack(anchor=tk.W,padx=10,pady=2)
        mf=self._lf(inner,'MISFIRE CYLINDER');mf.pack(fill=tk.X,padx=12,pady=6)
        mfi=tk.Frame(mf,bg=PANEL);mfi.pack(padx=6,pady=6)
        self._miss_v=tk.IntVar(value=0)
        for cyl,lbl in [(0,'None'),(1,'Cyl 1'),(2,'Cyl 2'),(3,'Cyl 3'),(4,'Cyl 4')]:
            tk.Radiobutton(mfi,text=lbl,variable=self._miss_v,value=cyl,bg=PANEL,fg=RED,selectcolor=DARK,font=('Courier',self._fl,'bold'),pady=6,command=lambda:setattr(self.eng,'fault_miss',self._miss_v.get())).pack(side=tk.LEFT,padx=8)
        tk.Label(mf,text='Misfire -> knock activity, rough idle, P030x DTC',bg=PANEL,fg=DIM,font=('Courier',self._fs)).pack(pady=3)
        self._btn(inner,'CLEAR ALL FAULTS',self._clear_faults,fg=RED,bg='#3a0000').pack(pady=14,padx=20,fill=tk.X)

    def _clear_faults(self):
        for attr,var in self._fault_vars.items():var.set(False);setattr(self.eng,attr,False)
        self._miss_v.set(0);self.eng.fault_miss=0
        messagebox.showinfo('Faults','All faults cleared')

    def _tick(self):
        s=self.eng.snap()
        self._H['afr'].append(s['afr']);self._H['stft'].append(s['stft'])
        self._H['ltft'].append(s['ltft']);self._H['egt'].append(s['egt'])
        self._H['rpm'].append(s['rpm']);self._H['knock'].append(s['klvl'])
        for key,(var,fmt) in self._sb.items():
            v=s.get(key,0)
            try:var.set(fmt.format(v))
            except:var.set(str(v))
        dtcs=s['active_dtcs']
        self._dtc_v.set('  DTCs: '+' | '.join(c for c,_ in dtcs) if dtcs else '  NO DTCs')
        self._sc_v.set(s['scenario'].upper())
        for key,(var,fmt) in self._lv.items():
            v=s.get(key,'?')
            try:var.set(fmt.format(v))
            except:var.set(str(v))
        if MPL and hasattr(self,'_max1'):
            x=list(range(len(self._H['afr'])))
            for ax in [self._max1,self._max2]:ax.clear()
            self._max1.plot(x,list(self._H['afr']),color=CYAN,lw=1.5)
            self._max1.axhline(14.7,color=WHITE,lw=0.8,linestyle='--')
            self._max1.set_facecolor(DARK);self._max1.set_title('AFR',fontsize=9,color=CYAN,pad=3)
            self._max1.grid(True,color='#1a2535',lw=0.5);self._max1.tick_params(colors=GRAY,labelsize=8)
            self._max2.plot(x,list(self._H['stft']),color=AMBER,lw=1.5,label='STFT')
            self._max2.plot(x,[s['ltft']]*len(x),color=RED,lw=1.2,linestyle='--',label='LTFT')
            self._max2.axhline(0,color=DIM,lw=0.8)
            self._max2.set_facecolor(DARK);self._max2.set_title('STFT/LTFT %',fontsize=9,color=AMBER,pad=3)
            self._max2.grid(True,color='#1a2535',lw=0.5);self._max2.tick_params(colors=GRAY,labelsize=8)
            self._max2.legend(fontsize=7,labelcolor=WHITE,loc='upper left')
            self._mfig.tight_layout(pad=0.5);self._mcv.draw()
        for i in self._obd_tv.get_children():self._obd_tv.delete(i)
        for m in list(self.obd.msgs)[-25:]:
            ts=time.strftime('%H:%M:%S',time.localtime(m['ts']))
            self._obd_tv.insert('','end',values=(ts,m['id'],m['dir'],m['data'],m['dec']))
        for i in self._j_tv.get_children():self._j_tv.delete(i)
        for m in list(self.j1939.msgs)[-30:]:
            ts=time.strftime('%H:%M:%S',time.localtime(m['ts']))
            self._j_tv.insert('','end',values=(ts,m['cid'],m['pgn'],m['name'],m['sa'],m['data'],m['dec']))
        if MPL and hasattr(self,'_sfig'):
            for color,ax,en,cb in [(GREEN,self._sax1,self._ch1_en,self._ch1),(AMBER,self._sax2,self._ch2_en,self._ch2)]:
                ax.clear();ax.set_facecolor('#030810');ax.grid(True,color='#081508',lw=0.9);ax.tick_params(colors=DIM,labelsize=9)
                if en.get():
                    res=self.scope.get(cb.get(),s)
                    if res:
                        t,y,ylabel,ymin,ymax=res
                        ax.plot(t*1000,y,color=color,lw=1.5);ax.set_ylabel(ylabel,fontsize=9,color=color)
                        ax.set_ylim(ymin,ymax);ax.set_xlabel('ms',fontsize=8,color=DIM)
            self._sinfo.set('RPM %.0f  PW %.2fms  DC %.1f%%  Adv %.1fdeg  %s'%(s['rpm'],s['pw'],s['dc'],s['adv'],s['scenario'].upper()))
            self._sfig.tight_layout(pad=0.5);self._scv.draw()
        if hasattr(self,'_op'):
            for key,(var,fmt) in self._op.items():
                v=s.get(key,0)
                try:var.set(fmt.format(v))
                except:var.set(str(v))
            self._ve_ed.cursor(s['rpm'],s['map_kpa'])
            self._ig_ed.cursor(s['rpm'],s['map_kpa'])
            self._afr_ed.cursor(s['rpm'],s['map_kpa'])
        if hasattr(self,'_sv'):
            for key,var in self._sv.items():
                v=s.get(key,'?')
                try:var.set('%.2f'%v if isinstance(v,float) else str(v))
                except:var.set(str(v))
        if MPL and hasattr(self,'_tax'):
            x=list(range(len(self._H['stft'])))
            for ax in self._tax:ax.clear()
            self._tax[0].plot(x,list(self._H['stft']),color=AMBER,lw=1.5,label='STFT')
            self._tax[0].plot(x,[s['ltft']]*len(x),color=RED,lw=1.2,linestyle='--',label='LTFT')
            self._tax[0].axhline(0,color=DIM,lw=0.8);self._tax[0].set_ylim(-28,28);self._tax[0].legend(fontsize=7,labelcolor=WHITE)
            self._tax[1].plot(x,list(self._H['egt']),color='#ff8844',lw=1.5)
            self._tax[2].plot(x,list(self._H['afr']),color=CYAN,lw=1.5)
            self._tax[2].axhline(14.7,color=WHITE,lw=0.8,linestyle='--')
            for ax,t,c in zip(self._tax,['Fuel Trims %','EGT deg C','AFR'],[AMBER,'#ff8844',CYAN]):
                ax.set_facecolor(DARK);ax.grid(True,color='#1a2535',lw=0.5);ax.tick_params(colors=GRAY,labelsize=8);ax.set_title(t,fontsize=9,color=c,pad=3)
            self._tfig.tight_layout(pad=0.5);self._tcv.draw()
        if self._log_on:
            row=(time.strftime('%H:%M:%S'),'%.0f'%s['rpm'],'%.0f'%s['map_kpa'],'%.1f'%s['tps'],
                 '%.0f'%s['clt'],'%.0f'%s['iat'],'%.2f'%s['afr'],'%.3f'%s['lam'],
                 '%.1f'%s['adv'],'%+.1f'%s['stft'],'%+.1f'%s['ltft'],'%.2f'%s['pw'],
                 '%.1f'%s['dc'],'%.2f'%s['klvl'],'%.0f'%s['egt'],str(s['gear']),s['scenario'])
            self._log_rows.append(row)
            self._log_tv.insert('','end',values=row)
            ch=self._log_tv.get_children()
            if len(ch)>500:self._log_tv.delete(ch[0])
            self._log_tv.yview_moveto(1)
        self.after(350,self._tick)


if __name__=='__main__':
    CyberKnife().mainloop()
