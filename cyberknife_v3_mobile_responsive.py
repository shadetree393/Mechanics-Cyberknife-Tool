#!/usr/bin/env python3
"""
MECHANIC'S CYBERKNIFE — Integrated Device Emulator v3.0
════════════════════════════════════════════════════════
Emulates the actual hardware device: one engine, one CAN bus,
one scope — all displays driven from the same source simultaneously.
Status bar always visible. Auto-polling like a real scanner.
Fault injection panel to generate real DTCs for testing.

Run:   python3 cyberknife_emulator_v3.py
Needs: pip install matplotlib numpy
"""
import tkinter as tk
from tkinter import ttk, messagebox
import random, time, threading, math
from collections import deque

try:
    import matplotlib
    try: matplotlib.use('TkAgg')
    except: matplotlib.use('Agg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import numpy as np
    try:
        from mpl_toolkits.mplot3d import Axes3D  # noqa
        AXES3D = True
    except ImportError:
        AXES3D = False
    MPL = True
except ImportError:
    MPL = False

# ── COLOUR PALETTE ──────────────────────────────────────
BG    = '#0d1117'; PANEL = '#161b22'; DARK  = '#0a0e14'
GREEN = '#00ff88'; AMBER = '#ffaa00'; RED   = '#ff4040'
BLUE  = '#4488ff'; CYAN  = '#00ccff'; YELL  = '#ffff44'
PURP  = '#cc55ff'; WHITE = '#ddeeff'; GRAY  = '#445566'
DIM   = '#223344'

# ════════════════════════════════════════════════════════
# SECTION 1 — ECU MAPS
# ════════════════════════════════════════════════════════
class ECUMaps:
    RPM_BINS = [500,1000,1500,2000,2500,3000,3500,4000,4500,5000,5500,6000]
    MAP_BINS = [20,30,40,50,60,70,80,90,100]
    def __init__(self):
        nr,nm = len(self.RPM_BINS),len(self.MAP_BINS)
        self.ve_table  = self._ve(nm,nr)
        self.ign_table = self._ign(nm,nr)
        self.afr_table = self._afr(nm,nr)
        self.clt_ax    = [-40,-20,0,20,40,60,80,90,100]
        self.clt_corr  = [180,160,140,120,110,105,100,100,98]
        self.iat_ax    = [-40,-20,0,20,40,60,80,100]
        self.iat_corr  = [112,108,105,100,96,91,85,78]
        self.dt_v      = [8,9,10,11,12,13,14,15]
        self.dt_ms     = [1.8,1.5,1.3,1.1,0.9,0.8,0.7,0.65]
        self.idle_cax  = [0,20,40,60,80,90]
        self.idle_rpm  = [1400,1200,1000,900,850,800]
        self.req_fuel       = 7.2
        self.soft_cut       = 6800; self.hard_cut = 7200
        self.accel_thresh   = 2.5;  self.accel_mult = 1.6; self.accel_dur = 350
        self.knock_step     = 2.5;  self.knock_max  = 12.0; self.knock_rec = 0.3
        self.fuel_psi       = 43.5
    def _ve(self,nm,nr):
        t=[]
        for mi in range(nm):
            row=[]; lf=mi/(nm-1)
            for ri in range(nr):
                b=math.exp(-0.5*((ri-6)/3.2)**2)
                row.append(round(max(20,min(108,38+62*lf*(0.55+0.45*b)+random.uniform(-1.5,1.5))),1))
            t.append(row)
        return t
    def _ign(self,nm,nr):
        t=[]
        for mi in range(nm):
            row=[]; lr=(mi/(nm-1))*0.45
            for ri in range(nr):
                b=8+ri*2*(1-lr); b=min(b,42*(1-lr*.7))
                row.append(round(max(0,b+random.uniform(-.3,.3)),1))
            t.append(row)
        return t
    def _afr(self,nm,nr):
        t=[]
        for mi in range(nm):
            row=[]; lf=mi/(nm-1)
            for ri in range(nr):
                if lf>.85: v=12.5+(ri/(nr-1))*.8
                elif lf<.25: v=15.2+(ri/(nr-1))*.4
                else: v=14.7+random.uniform(-.1,.1)
                row.append(round(v,1))
            t.append(row)
        return t
    def interp2d(self,tbl,rpm,kpa):
        ri=self._i(self.RPM_BINS,rpm); mi=self._i(self.MAP_BINS,kpa)
        r0=max(0,ri-1);r1=min(len(self.RPM_BINS)-1,ri)
        m0=max(0,mi-1);m1=min(len(self.MAP_BINS)-1,mi)
        rx=max(0,min(1,(rpm-self.RPM_BINS[r0])/max(self.RPM_BINS[r1]-self.RPM_BINS[r0],1)))
        mx=max(0,min(1,(kpa-self.MAP_BINS[m0])/max(self.MAP_BINS[m1]-self.MAP_BINS[m0],1)))
        return (tbl[m0][r0]*(1-rx)*(1-mx)+tbl[m0][r1]*rx*(1-mx)+
                tbl[m1][r0]*(1-rx)*mx    +tbl[m1][r1]*rx*mx)
    def interp1d(self,xs,ys,v):
        if v<=xs[0]: return ys[0]
        if v>=xs[-1]: return ys[-1]
        for i in range(len(xs)-1):
            if xs[i]<=v<=xs[i+1]:
                f=(v-xs[i])/(xs[i+1]-xs[i]); return ys[i]+f*(ys[i+1]-ys[i])
        return ys[-1]
    def _i(self,bins,v):
        for i,b in enumerate(bins):
            if v<=b: return i
        return len(bins)-1


# ════════════════════════════════════════════════════════
# SECTION 2 — ENGINE PHYSICS (single source of truth)
# ════════════════════════════════════════════════════════
class EnginePhysics:
    GEARS=[0,3.5,2.0,1.35,0.98,0.75]; FD=3.73; TIRE=1.98
    def __init__(self,maps):
        self.m=maps; self._lk=threading.Lock()
        # ── state
        self.rpm=800.0;  self.map_kpa=35.0; self.tps_pct=0.0
        self.clt_c=20.0; self.iat_c=25.0;   self.batt_v=12.6
        self.gear=0;     self.spd=0.0
        # ── outputs
        self.afr=14.7; self.lam=1.0; self.pw_ms=3.0; self.dc=0.0
        self.dwell=3.5; self.adv=10.0; self.egt=600.0; self.oil=45.0
        # ── trims
        self.stft=0.0; self.ltft=0.0; self.ego=False
        # ── knock
        self.kret=0.0; self.klvl=0.0; self.kcnt=0
        # ── accel enrich
        self._at=0.0; self._ptps=0.0; self._ptt=time.time()
        # ── DTCs
        self.active_dtcs=[]; self.stored_dtcs=[]
        # ── scenario
        self.scenario='warmup'; self._st=0.0; self._rtgt=850.0
        # ── FAULT INJECTION FLAGS (set from UI)
        self.fault_o2_dead    = False   # O2 sensor unplugged — open loop
        self.fault_map_stuck  = False   # MAP sensor stuck at 50kPa
        self.fault_clt_short  = False   # CLT shorted to ground — reads -40°C
        self.fault_miss_cyl   = 0       # cylinder number misfiring (0=none, 1-4)
        self.fault_lean_vac   = False   # vacuum leak — leans out mixture
        self.fault_ign_retard = False   # ignition timing 10° retard (e.g. bad knock sensor)
        self.fault_inj_stuck  = False   # stuck-open injector — always rich
        self._run=True
        threading.Thread(target=self._loop,daemon=True).start()

    def _loop(self):
        dt=0.08
        while self._run:
            time.sleep(dt)
            with self._lk: self._step(dt)

    def _step(self,dt):
        self._st+=dt; self._scenario(); m=self.m
        # RPM inertia
        self.rpm+=((self._rtgt-self.rpm)*3.0*dt+random.gauss(0,self.rpm*.003))
        self.rpm=max(0,min(8500,self.rpm))
        # MAP
        map_tgt=max(15,min(105,20+self.tps_pct*.78-(self.rpm/6000)*8))
        if self.fault_map_stuck: map_tgt=50.0      # FAULT: stuck MAP
        if self.fault_lean_vac:  map_tgt+=8.0      # FAULT: vacuum leak adds load signal
        self.map_kpa+=(map_tgt-self.map_kpa)*5*dt; self.map_kpa=max(15,min(105,self.map_kpa))
        # ── FUEL CALC
        ve      = m.interp2d(m.ve_table,self.rpm,self.map_kpa)
        afr_tgt = m.interp2d(m.afr_table,self.rpm,self.map_kpa)
        clt_c   = -40.0 if self.fault_clt_short else self.clt_c
        cc      = m.interp1d(m.clt_ax,m.clt_corr,clt_c)/100
        ic      = m.interp1d(m.iat_ax,m.iat_corr,self.iat_c)/100
        dead    = m.interp1d(m.dt_v,m.dt_ms,self.batt_v)
        # accel enrich
        now=time.time()
        rate=(self.tps_pct-self._ptps)/max(now-self._ptt,.001)*.1
        self._ptps=self.tps_pct; self._ptt=now
        if rate>m.accel_thresh: self._at=m.accel_dur/1000
        am=1.0
        if self._at>0: am=1+(m.accel_mult-1)*(self._at/(m.accel_dur/1000)); self._at=max(0,self._at-dt)
        # stuck injector overrides pulse width
        if self.fault_inj_stuck:
            self.pw_ms=99.0; self.dc=100.0
        else:
            ego_t=1+(self.stft+self.ltft)/100
            self.pw_ms=m.req_fuel*(ve/100)*(14.7/afr_tgt)*cc*ic*am*ego_t+dead
            if self.rpm>=m.hard_cut: self.pw_ms=0
            elif self.rpm>=m.soft_cut and random.random()<.5: self.pw_ms=0
            cy=120000/max(self.rpm,100); self.dc=min(100,(self.pw_ms/cy)*100)
        # ── IGNITION
        ign_base=m.interp2d(m.ign_table,self.rpm,self.map_kpa)
        if self.fault_ign_retard: ign_base=max(0,ign_base-10)
        risk=max(0,(ign_base-25)/15)*(self.map_kpa/100)*(self.rpm/6000)
        # misfire adds mechanical knock
        if self.fault_miss_cyl>0 and random.random()<.15: risk+=0.4
        if random.random()<risk*.08:
            self.kret=min(self.kret+m.knock_step,m.knock_max)
            self.klvl=min(1,self.klvl+.4); self.kcnt+=1
        else:
            self.kret=max(0,self.kret-m.knock_rec*dt*10); self.klvl=max(0,self.klvl-.05)
        self.adv=max(0,ign_base-self.kret)
        self.dwell=max(1.5,(3.8*(13.5/max(self.batt_v,8)))-self.rpm*.0001)
        # ── ACTUAL AFR
        lean_offset=1.5 if self.fault_lean_vac else 0   # vacuum leak leans mixture
        if self.fault_o2_dead:
            self.afr=afr_tgt+lean_offset+random.gauss(0,.3)  # open loop drift
            self.ego=False
        elif self.fault_inj_stuck:
            self.afr=random.uniform(10.2,11.5)  # stuck open = very rich
            self.ego=False
        else:
            err=random.gauss(0,1.5)/100*afr_tgt
            self.afr=max(10,min(20,afr_tgt+lean_offset+err+random.gauss(0,.05)))
        self.lam=self.afr/14.7
        # ── EGO trims (closed loop)
        if not self.fault_o2_dead and self.clt_c>75 and self.tps_pct<80 and self.rpm<4500:
            self.ego=True
            self.stft+=(afr_tgt-self.afr)*.8*dt; self.stft=max(-25,min(25,self.stft))
            self.ltft+=self.stft*.003*dt;          self.ltft=max(-25,min(25,self.ltft))
        else:
            if not self.fault_o2_dead: self.stft*=.95
        # ── EGT
        self.egt=max(300,min(1050,450+(self.rpm/6000)*350+(self.map_kpa/100)*200+(self.lam-1)*150+random.gauss(0,5)))
        # ── CLT warmup
        clt_act=-40 if self.fault_clt_short else self.clt_c
        if self.fault_clt_short:
            self.clt_c=-40+random.gauss(0,.5)
        elif self.clt_c<90:
            self.clt_c+=((self.rpm/6000)*.4+(self.map_kpa/100)*.2)*dt
        else:
            self.clt_c=87+random.gauss(0,1)
        # ── IAT, batt, speed, oil
        self.iat_c+=(25+self.rpm*.003-self.iat_c)*.01*dt+random.gauss(0,.1)
        tv=14.2 if self.rpm>900 else 12.0
        self.batt_v=max(10,min(15,self.batt_v+(tv-self.batt_v)*dt+random.gauss(0,.02)))
        self.spd=self.rpm/(self.GEARS[min(self.gear,5)]*self.FD)*self.TIRE*60/1000 if 0<self.gear<=5 else 0
        self.oil=max(0,min(90,0 if self.rpm<100 else 10+(self.rpm/6000)*60+random.gauss(0,1)))
        # ── DTCs
        self._dtcs()
        # ── idle target
        if self.tps_pct<1:
            self._rtgt=m.interp1d(m.idle_cax,m.idle_rpm,self.clt_c)+random.gauss(0,20)

    def _scenario(self):
        c=self._st%150
        if   c<20:  self.scenario='warmup'; self.tps_pct=.5+random.gauss(0,.3); self.gear=0
        elif c<40:  self.scenario='cruise'; self.tps_pct=22+math.sin(self._st*.1)*5; self.gear=3; self._rtgt=2200+math.sin(self._st*.08)*300
        elif c<60:  self.scenario='wot';    self.tps_pct=98+random.gauss(0,.5); self.gear=2; self._rtgt=min(7000,self._rtgt+50)
        elif c<80:  self.scenario='decel';  self.tps_pct=0; self.gear=4; self._rtgt=max(800,self._rtgt-80)
        elif c<100: self.scenario='hwy';    self.tps_pct=35+random.gauss(0,2); self.gear=4; self._rtgt=3000+random.gauss(0,100)
        else:       self.scenario='idle';   self.tps_pct=.2+random.gauss(0,.2); self.gear=0; self._rtgt=850
        self.tps_pct=max(0,min(100,self.tps_pct))

    def _dtcs(self):
        checks=[
            (self.batt_v<11,         'P0562','System Voltage Low'),
            (self.oil<8 and self.rpm>500,'P0520','Oil Pressure Sensor'),
            (self.ltft>20,           'P0171','Fuel Trim Lean B1'),
            (self.ltft<-20,          'P0172','Fuel Trim Rich B1'),
            (self.kcnt>50,           'P0325','Knock Sensor Circuit'),
            (self.clt_c>115,         'P0118','Coolant Temp High'),
            (self.egt>950,           'P0545','EGT Sensor High'),
            (self.fault_o2_dead,     'P0131','O2 Sensor No Activity'),
            (self.fault_miss_cyl>0,  f'P030{self.fault_miss_cyl}',f'Cyl {self.fault_miss_cyl} Misfire'),
            (self.fault_clt_short,   'P0117','CLT Sensor Low'),
            (self.fault_inj_stuck,   'P0201','Injector Circuit Shorted'),
            (abs(self.stft)>22,      'P0300','Multiple Misfire / Fuel Control'),
        ]
        for cond,code,desc in checks:
            if cond and code not in [d[0] for d in self.active_dtcs]:
                self.active_dtcs.append((code,desc))
                if code not in [d[0] for d in self.stored_dtcs]:
                    self.stored_dtcs.append((code,desc))
        # Clear DTCs that have recovered
        self.active_dtcs=[d for d in self.active_dtcs if self._still_active(d[0])]

    def _still_active(self,code):
        if code=='P0562': return self.batt_v<11
        if code=='P0520': return self.oil<8 and self.rpm>500
        if code=='P0171': return self.ltft>20
        if code=='P0172': return self.ltft<-20
        if code=='P0131': return self.fault_o2_dead
        if code.startswith('P030') and len(code)==5 and code[4].isdigit(): return self.fault_miss_cyl>0
        if code=='P0117': return self.fault_clt_short
        if code=='P0201': return self.fault_inj_stuck
        return True

    def snap(self):
        with self._lk:
            ve=self.m.interp2d(self.m.ve_table,self.rpm,self.map_kpa)
            ig=self.m.interp2d(self.m.ign_table,self.rpm,self.map_kpa)
            af=self.m.interp2d(self.m.afr_table,self.rpm,self.map_kpa)
            return dict(rpm=self.rpm,map_kpa=self.map_kpa,tps=self.tps_pct,
                clt=self.clt_c,iat=self.iat_c,batt=self.batt_v,
                afr=self.afr,lam=self.lam,pw=self.pw_ms,dc=self.dc,
                dwell=self.dwell,adv=self.adv,egt=self.egt,oil=self.oil,
                stft=self.stft,ltft=self.ltft,ego=self.ego,
                kret=self.kret,klvl=self.klvl,spd=self.spd,gear=self.gear,
                accel=self._at>0,scenario=self.scenario,
                active_dtcs=list(self.active_dtcs),
                stored_dtcs=list(self.stored_dtcs),
                ve_live=ve,ign_live=ig,afr_tgt=af,
                # faults
                fault_o2=self.fault_o2_dead,fault_map=self.fault_map_stuck,
                fault_clt=self.fault_clt_short,fault_miss=self.fault_miss_cyl,
                fault_lean=self.fault_lean_vac,fault_ign=self.fault_ign_retard,
                fault_inj=self.fault_inj_stuck)


# ════════════════════════════════════════════════════════
# SECTION 3 — J1939 BUS (driven by engine state)
# ════════════════════════════════════════════════════════
class J1939Bus:
    SA_ENG=0x00; SA_TRANS=0x03; SA_TOOL=0xF9
    def __init__(self,eng):
        self.eng=eng; self.msgs=deque(maxlen=400)
        threading.Thread(target=self._loop,daemon=True).start()
    def _id(self,p,pgn,sa): return ((p&7)<<26)|(pgn<<8)|(sa&0xFF)
    def _loop(self):
        while True:
            time.sleep(0.05); s=self.eng.snap(); t=time.time()
            # EEC1 — RPM, torque  20ms
            if random.random()<.4:
                r=int(s['rpm']/.125); tq=min(100,int(s['map_kpa']*.9))
                self._pub(t,self._id(3,0xF004,self.SA_ENG),'61444','EEC1 Engine Ctrl','Engine',
                    [0xFF,tq,0xFF,r&0xFF,(r>>8)&0xFF,0xFF,0xFF,0xFF],f"RPM={s['rpm']:.0f}  Torque={tq}%")
            # EEC2 — TPS, load  20ms
            if random.random()<.4:
                tp=int(s['tps']/.4); ld=int(s['map_kpa']*.64)
                self._pub(t,self._id(3,0xF003,self.SA_ENG),'61443','EEC2 Throttle','Engine',
                    [0xFF,tp&0xFF,ld&0xFF,0xFF,0xFF,0xFF,0xFF,0xFF],f"TPS={s['tps']:.1f}%  MAP={s['map_kpa']:.0f}kPa")
            # ET1 — Temps  1s
            if random.random()<.1:
                self._pub(t,self._id(6,0xFEEE,self.SA_ENG),'65262','ET1 Temps','Engine',
                    [int(s['clt']+40),0xFF,int(s['iat']+40),0xFF,0xFF,0xFF,0xFF,0xFF],
                    f"CLT={s['clt']:.0f}C  IAT={s['iat']:.0f}C")
            # CCVS — speed  100ms
            if random.random()<.2:
                sp=int(s['spd']/.00390625)
                self._pub(t,self._id(6,0xFEF1,self.SA_ENG),'65265','CCVS Speed','Engine',
                    [0xFF,sp&0xFF,(sp>>8)&0xFF,0xFF,0xFF,0xFF,0xFF,0xFF],f"Spd={s['spd']:.1f}km/h")
            # EFL/P1 — pressures  1s
            if random.random()<.1:
                self._pub(t,self._id(6,0xFEEF,self.SA_ENG),'65263','EFL/P1 Press','Engine',
                    [int(s['oil']*4)&0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF],f"Oil={s['oil']:.0f}psi")
            # DM1 — active DTCs
            if s['active_dtcs'] and random.random()<.04:
                code,desc=s['active_dtcs'][0]
                self._pub(t,self._id(6,0xFECA,self.SA_ENG),'65226','DM1 Active DTC','Engine',
                    [0x04,0x00,0x11,0x22,0x00,0xFF,0xFF,0xFF],f"FAULT: {code} {desc}")
    def _pub(self,t,cid,pgn,name,sa,data,dec):
        self.msgs.append(dict(ts=t,cid=f"0x{cid:08X}",pgn=pgn,name=name,sa=sa,
            data=' '.join(f'{b:02X}' for b in data),dec=dec))

# ════════════════════════════════════════════════════════
# SECTION 4 — OBD-II HANDLER (auto-poll + manual)
# ════════════════════════════════════════════════════════
class OBDHandler:
    PIDS={
        0x04:('Engine Load %',    lambda s: f"{min(100,s['tps']*.7+s['map_kpa']*.2):.0f} %"),
        0x05:('Coolant Temp',     lambda s: f"{s['clt']:.0f} C  ({s['clt']*1.8+32:.0f} F)"),
        0x06:('STFT Bank1',       lambda s: f"{s['stft']:+.1f} %"),
        0x07:('LTFT Bank1',       lambda s: f"{s['ltft']:+.1f} %"),
        0x0B:('MAP Pressure',     lambda s: f"{s['map_kpa']:.0f} kPa"),
        0x0C:('Engine RPM',       lambda s: f"{s['rpm']:.0f} RPM"),
        0x0D:('Vehicle Speed',    lambda s: f"{s['spd']:.0f} km/h  ({s['spd']*.621:.0f} mph)"),
        0x0E:('Timing Advance',   lambda s: f"{s['adv']:.1f} deg BTDC"),
        0x0F:('Intake Air Temp',  lambda s: f"{s['iat']:.0f} C"),
        0x11:('Throttle Pos',     lambda s: f"{s['tps']:.1f} %"),
        0x44:('Fuel-Air Equiv',   lambda s: f"{s['lam']:.3f} lambda  ({s['afr']:.2f}:1)"),
        0x5C:('Oil Temp',         lambda s: f"{s['clt']+5:.0f} C"),
    }
    def __init__(self,eng):
        self.eng=eng; self.msgs=deque(maxlen=400)
        self.autopoll=False; self._poll_pids=[0x0C,0x05,0x0B,0x11,0x0E,0x06,0x07]
        self._poll_idx=0
        threading.Thread(target=self._autopoll_loop,daemon=True).start()
    def _autopoll_loop(self):
        while True:
            time.sleep(0.4)
            if self.autopoll:
                pid=self._poll_pids[self._poll_idx%len(self._poll_pids)]
                self.request(0x01,pid); self._poll_idx+=1
    def request(self,mode,pid=None):
        s=self.eng.snap(); t=time.time()
        req=f"02 {mode:02X} {pid:02X} 00 00 00 00 00" if pid else f"01 {mode:02X} 00 00 00 00 00 00"
        self.msgs.append(dict(ts=t,id='0x7DF',dir='TX->',data=req,dec=f"REQ Mode {mode:02X}h"+(f" PID {pid:02X}h" if pid else '')))
        rm=mode+0x40; resp=None; result=''
        if mode==0x01 and pid in self.PIDS:
            name,fn=self.PIDS[pid]; result=f"[{pid:02X}h] {name} = {fn(s)}"
            resp=[0x03,rm,pid,0,0,0,0,0]
        elif mode==0x03:
            dtcs=s['active_dtcs']
            result='Active DTCs: '+', '.join(f"{c} {d}" for c,d in dtcs) if dtcs else 'No active DTCs — clear'
            resp=[0x02,rm,len(dtcs),0,0,0,0,0]
        elif mode==0x04:
            with self.eng._lk:
                self.eng.active_dtcs.clear(); self.eng.stft=0; self.eng.ltft=0; self.eng.kcnt=0
            result='DTCs CLEARED — trims reset'; resp=[0x01,rm,0,0,0,0,0,0]
        elif mode==0x07:
            dtcs=s['stored_dtcs']
            result='Pending: '+', '.join(f"{c} {d}" for c,d in dtcs) if dtcs else 'No pending DTCs'
            resp=[0x02,rm,len(dtcs),0,0,0,0,0]
        elif mode==0x09 and pid==0x02:
            result='VIN: 1FTFW1ED3MFB12345  (Ford F-150 2021)'; resp=[0x01,rm,pid,0,0,0,0,0]
        if resp:
            self.msgs.append(dict(ts=time.time(),id='0x7E8',dir='<-RX',
                data=' '.join(f'{b:02X}' for b in resp),dec=result))
        return result


# ════════════════════════════════════════════════════════
# SECTION 5 — SCOPE WAVEFORM GENERATOR
# ════════════════════════════════════════════════════════
class ScopeGen:
    SIGS=['Crank 60-2 VR','Crank 60-2 Hall','Cam Hall',
          'Injector Primary','Ignition Primary',
          'CAN High 500k','CAN Low 500k',
          'MAP Sensor 0-5V','Wideband O2 CJ125','Narrowband O2',
          'TPS Potentiometer','Battery/Alternator',
          'Injector Duty Cycle','Knock Sensor Piezo','Fuel Pump PWM']
    def get(self,sig,s,n=180):
        if not MPL: return None
        rpm=max(100,s['rpm']); t=np.linspace(0,0.1,n)
        if 'VR'      in sig: return self._vr(t,rpm)
        if 'Hall' in sig and 'Cam' not in sig: return self._hall(t,rpm)
        if 'Cam'     in sig: return self._cam(t,rpm)
        if 'Injector P' in sig: return self._inj(t,rpm,s['pw'])
        if 'Ignition'in sig: return self._ign(t,rpm,s['dwell'])
        if 'CAN High'in sig: return self._can(t,'H')
        if 'CAN Low' in sig: return self._can(t,'L')
        if 'MAP'     in sig: return self._map(t,s['map_kpa'])
        if 'Wideband'in sig: return self._wb(t,s['lam'])
        if 'Narrow'  in sig: return self._nb(t,s['lam'])
        if 'TPS'     in sig: return self._tps(t,s['tps'])
        if 'Battery' in sig: return self._batt(t,s['batt'])
        if 'Duty'    in sig: return self._dc(t,rpm,s['pw'])
        if 'Knock'   in sig: return self._knock(t,s['klvl'])
        if 'Fuel Pump'in sig: return self._fp(t)
        return t,np.zeros(n),'V',-1,1
    def _vr(self,t,rpm):
        p=60/rpm; sig=np.zeros_like(t)
        for i,ti in enumerate(t):
            a=(ti%p)/p; tf=a*60; tn=int(tf)%60; tp=tf%1
            if tn>=58: sig[i]=math.sin(tp*math.pi*2)*4.5*(1 if tp<.5 else -1)
            else:       sig[i]=math.exp(-tp*8)*math.sin(tp*math.pi*6)*2.5
        return t,sig+np.random.normal(0,.08,len(t)),'V (VR)',-6,6
    def _hall(self,t,rpm):
        p=60/rpm; sig=np.zeros_like(t)
        for i,ti in enumerate(t):
            a=(ti%p)/p; tf=a*60; tn=int(tf)%60; tp=tf%1
            sig[i]=0 if tn>=58 else (5 if tp<.5 else 0)
        return t,sig+np.random.normal(0,.04,len(t)),'V (Hall)',-.5,6
    def _cam(self,t,rpm):
        p=120/rpm; sig=np.zeros_like(t)
        for i,ti in enumerate(t):
            ph=(ti%p)/p; sig[i]=5 if .05<ph<.22 else 0
        return t,sig+np.random.normal(0,.03,len(t)),'V (Cam)',-.5,6
    def _inj(self,t,rpm,pw):
        ip=0.12/max(1,rpm/1000); pw=pw/1000; sig=np.zeros_like(t)
        for i,ti in enumerate(t):
            ph=ti%ip
            if ph<pw: sig[i]=12.2+np.random.normal(0,.1)
            elif ph<pw+.0003:
                f=(ph-pw)/.0003; sig[i]=12+52*math.exp(-f*8)*math.sin(f*math.pi*4)
            else: sig[i]=np.random.normal(0,.05)
        return t,sig,'V (Inj)',-5,70
    def _ign(self,t,rpm,dw):
        ip=120/rpm/4; dw=dw/1000; sig=np.zeros_like(t)
        for i,ti in enumerate(t):
            ph=ti%ip
            if ph<dw: sig[i]=12-(ph/dw)*.5
            elif ph<dw+.0001:
                f=(ph-dw)/.0001; sig[i]=12-f*200
            elif ph<dw+.0008:
                f=(ph-dw-.0001)/.0007
                sig[i]=-60*math.exp(-f*12)*math.cos(f*math.pi*20)
            else: sig[i]=np.random.normal(0,.05)
        return t,sig,'V (Coil)',-80,20
    def _can(self,t,ch):
        bits=[0,0,0,0,1,1,1,0,1,0,1,0,1,1,0,0,1,0,1,1,1,0,0,0,1,0,0,1]
        bt=2e-6; sig=np.full_like(t,2.5)
        for i,ti in enumerate(t):
            dom=bits[int(ti/bt)%len(bits)]==0
            sig[i]=(3.5 if dom else 2.5) if ch=='H' else (1.5 if dom else 2.5)
            sig[i]+=np.random.normal(0,.03)
        lbl='CAN-H 3.5V' if ch=='H' else 'CAN-L 1.5V'
        return t,sig,lbl,0,5
    def _map(self,t,kpa):
        b=0.5+4*(kpa/100)
        return t,np.full_like(t,b)+.05*np.sin(t*2*math.pi*25)+np.random.normal(0,.015,len(t)),'V MAP',0,5
    def _wb(self,t,lam):
        b=2.45+(lam-1)*-2
        return t,np.clip(np.full_like(t,b)+np.random.normal(0,.015,len(t)),.1,4.9),'V WB',0,5
    def _nb(self,t,lam):
        sig=np.zeros_like(t)
        for i,ti in enumerate(t):
            c=math.sin(ti*math.pi*5)
            if lam<1: sig[i]=.85+.05*c
            elif lam>1.05: sig[i]=.15-.05*c
            else: sig[i]=.5+.4*math.tanh(c*5)
            sig[i]+=np.random.normal(0,.02)
        return t,sig,'V NB O2',0,1.1
    def _tps(self,t,tps):
        return t,np.full_like(t,.5+tps*.04)+np.random.normal(0,.01,len(t)),f'V TPS {tps:.0f}%',0,5
    def _batt(self,t,v):
        return t,np.full_like(t,v)+np.random.normal(0,.05,len(t))+.15*np.sin(t*2*math.pi*120),'V Batt',10,16
    def _dc(self,t,rpm,pw):
        if rpm<100: return t,np.zeros_like(t),'Duty%',0,110
        cy=120000/rpm; dc=min(100,(pw/cy)*100); p=60/rpm*2; sig=np.zeros_like(t)
        for i,ti in enumerate(t): sig[i]=dc if (ti%p)/p<dc/100 else 0
        return t,sig,f'Duty {dc:.1f}%',0,110
    def _knock(self,t,kl):
        sig=np.random.normal(0,.05,len(t))
        if kl>.1: sig+=kl*2.5*np.sin(t*2*math.pi*7200)*np.exp(-t*50*kl)
        return t,sig,'V Knock',-3,3
    def _fp(self,t):
        sig=np.zeros_like(t)
        for i,ti in enumerate(t): sig[i]=12 if (ti*100)%1<.75 else 0
        return t,sig+np.random.normal(0,.05,len(t)),'V FP PWM',-.5,13

# ════════════════════════════════════════════════════════
# SECTION 6 — MAP EDITOR WIDGET
# ════════════════════════════════════════════════════════
class MapEditor(ttk.Frame):
    def __init__(self,parent,maps,attr,title,unit,vmin,vmax,**kw):
        super().__init__(parent,**kw); self.maps=maps; self.attr=attr
        self.title=title; self.unit=unit; self.vmin=vmin; self.vmax=vmax
        self._cells={}; self._cur=(0,0); self._build()
    def _build(self):
        ttk.Label(self,text=self.title,font=('Courier',9,'bold')).grid(row=0,column=0,columnspan=15,pady=3)
        ttk.Label(self,text='MAP↓  RPM→',font=('Courier',7),foreground=GRAY).grid(row=1,column=0)
        for ci,rpm in enumerate(ECUMaps.RPM_BINS):
            ttk.Label(self,text=str(rpm),font=('Courier',8),foreground='#88aacc').grid(row=1,column=ci+1,padx=1)
        for mi in range(len(ECUMaps.MAP_BINS)-1,-1,-1):
            vr=len(ECUMaps.MAP_BINS)-mi+1
            ttk.Label(self,text=str(ECUMaps.MAP_BINS[mi]),font=('Courier',7),foreground='#88aacc').grid(row=vr,column=0,padx=3)
            tbl=getattr(self.maps,self.attr)
            for ri in range(len(ECUMaps.RPM_BINS)):
                e=tk.Entry(self,width=5,font=('Courier',9),justify='center')
                e.insert(0,str(tbl[mi][ri])); e.grid(row=vr,column=ri+1,padx=1,pady=1)
                e.bind('<Return>',  lambda ev,m=mi,r=ri: self._edit(m,r))
                e.bind('<FocusOut>',lambda ev,m=mi,r=ri: self._edit(m,r))
                self._cells[(mi,ri)]=e; self._color(mi,ri,tbl[mi][ri])
    def _color(self,mi,ri,v):
        ratio=max(0,min(1,(v-self.vmin)/max(self.vmax-self.vmin,1)))
        if   ratio<.25: r=0;   g=int(ratio*4*200); b=220
        elif ratio<.5:  r=0;   g=200;               b=int((.5-ratio)*4*220)
        elif ratio<.75: r=int((ratio-.5)*4*255);g=200;b=0
        else:           r=255; g=int((1-ratio)*4*200);b=0
        bg=f'#{r:02x}{g:02x}{b:02x}'; fg='#000' if (.299*r+.587*g+.114*b)>140 else '#fff'
        c=self._cells.get((mi,ri))
        if c: c.config(background=bg,foreground=fg)
    def _edit(self,mi,ri):
        c=self._cells.get((mi,ri));
        if not c: return
        try:
            v=float(c.get()); tbl=getattr(self.maps,self.attr)
            tbl[mi][ri]=round(v,1); self._color(mi,ri,v)
        except: pass
    def cursor(self,rpm,kpa):
        rb=ECUMaps.RPM_BINS; mb=ECUMaps.MAP_BINS
        ri=min(range(len(rb)),key=lambda i:abs(rb[i]-rpm))
        mi=min(range(len(mb)),key=lambda i:abs(mb[i]-kpa))
        om,or_=self._cur; tbl=getattr(self.maps,self.attr)
        if 0<=om<len(tbl) and 0<=or_<len(tbl[0]): self._color(om,or_,tbl[om][or_])
        self._cur=(mi,ri); c=self._cells.get((mi,ri))
        if c: c.config(background='#ffffff',foreground='#000',font=('Courier',7,'bold'))
    def show3d(self):
        if not MPL: return
        try:
            from mpl_toolkits.mplot3d import Axes3D as A3D  # noqa
        except ImportError:
            messagebox.showinfo('3D','Install mpl_toolkits for 3D view\npip install matplotlib'); return
        win=tk.Toplevel(self); win.title(f'3D — {self.title}')
        fig=Figure(figsize=(6,4)); ax=fig.add_subplot(111,projection='3d')
        tbl=getattr(self.maps,self.attr)
        XX,YY=np.meshgrid(ECUMaps.RPM_BINS,ECUMaps.MAP_BINS)
        surf=ax.plot_surface(XX,YY,np.array(tbl),cmap='jet',edgecolor='none',alpha=.9)
        fig.colorbar(surf,ax=ax,shrink=.4,pad=.1)
        ax.set_xlabel('RPM',fontsize=8); ax.set_ylabel('MAP kPa',fontsize=8); ax.set_zlabel(self.unit,fontsize=8)
        ax.set_title(self.title,fontsize=9); ax.tick_params(labelsize=7)
        FigureCanvasTkAgg(fig,master=win).get_tk_widget().pack(fill=tk.BOTH,expand=True)


# ════════════════════════════════════════════════════════
# SECTION 7 — MAIN APP  (responsive mobile UI)
# Portrait:  controls compact-top, graphs fill below
# Landscape: narrow sidebar left, graphs fill right
# Figures:   sized from real frame pixels, resize on rotate
# ════════════════════════════════════════════════════════
import tkinter as tk
from tkinter import ttk, messagebox

BG    = '#0d1117'; PANEL = '#161b22'; DARK  = '#0a0e14'
GREEN = '#00ff88'; AMBER = '#ffaa00'; RED   = '#ff4040'
BLUE  = '#4488ff'; CYAN  = '#00ccff'; YELL  = '#ffff44'
PURP  = '#cc55ff'; WHITE = '#ddeeff'; GRAY  = '#445566'
DIM   = '#223344'

class CyberKnife(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CYBERKNIFE v3.0")
        try: self.attributes("-fullscreen", True)
        except: pass
        self.configure(bg=BG)

        self.maps  = ECUMaps()
        self.eng   = EnginePhysics(self.maps)
        self.j1939 = J1939Bus(self.eng)
        self.obd   = OBDHandler(self.eng)
        self.scope = ScopeGen()

        self._H = {k: deque(maxlen=200) for k in
                   ['afr','rpm','knock','stft','ltft','egt','oil','tps','adv']}

        # Screen metrics — read once, used for all sizing
        self.update_idletasks()
        self.SW = self.winfo_screenwidth()
        self.SH = self.winfo_screenheight()
        # Font scale: base on shorter screen dimension
        short = min(self.SW, self.SH)
        self._fs  = max(9,  int(short / 45))   # standard body font
        self._fsl = max(11, int(short / 36))   # label/button font
        self._fsg = max(14, int(short / 28))   # gauge font
        self._fsb = max(13, int(short / 32))   # big gauge font

        self._style()
        self._build_statusbar()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._tab_mechanic()
        self._tab_scope()
        self._tab_can()
        self._tab_tuning()
        self._tab_corrections()
        self._tab_sensors()
        self._tab_datalog()
        self._tab_faults()

        # Orientation-aware resize
        self._last_orient = None
        self.bind('<Configure>', self._on_resize)
        self.after(400, self._tick)

    # ── STYLE ──────────────────────────────────────────
    def _style(self):
        fs = self._fs; fl = self._fsl
        s = ttk.Style(); s.theme_use('clam')
        s.configure('TNotebook',            background=BG)
        s.configure('TNotebook.Tab',        background=PANEL, foreground='#aaccff',
                    padding=[int(self.SW/60), int(self.SH/80)],
                    font=('Courier', fl, 'bold'))
        s.map('TNotebook.Tab',              background=[('selected','#0f3460')])
        s.configure('TFrame',               background=BG)
        s.configure('TLabelframe',          background=PANEL, foreground='#aaccff')
        s.configure('TLabelframe.Label',    background=PANEL, foreground=GREEN,
                    font=('Courier', fs, 'bold'))
        s.configure('TLabel',               background=PANEL, foreground=WHITE)
        s.configure('Treeview',             font=('Courier', fs),
                    rowheight=max(22, int(self.SH/36)), background=DARK,
                    foreground=WHITE, fieldbackground=DARK)
        s.configure('Treeview.Heading',     font=('Courier', fs, 'bold'),
                    background=PANEL, foreground=CYAN)
        s.configure('TScrollbar',           background=PANEL)
        s.configure('TCombobox',            font=('Courier', fl))
        s.configure('TCheckbutton',         background=PANEL, foreground=WHITE,
                    font=('Courier', fl, 'bold'))

    # ── helpers ────────────────────────────────────────
    def _lf(self, parent, text):
        f = ttk.LabelFrame(parent, text=f' {text} ')
        return f

    def _btn(self, parent, text, cmd, fg=WHITE, bg='#0f3460'):
        h = max(2, int(self.SH / 120))
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg=fg,
                         font=('Courier', self._fsl, 'bold'),
                         relief='flat', pady=h, cursor='hand2')

    def _scrollframe(self, parent):
        """Returns (outer_frame, inner_frame) — inner_frame is scrollable."""
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0,0), window=inner, anchor='nw')
        def _on_frame_conf(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        inner.bind('<Configure>', _on_frame_conf)
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        return canvas, inner

    def _orient(self):
        w = self.winfo_width(); h = self.winfo_height()
        if w < 10 or h < 10:
            w, h = self.SW, self.SH
        return 'landscape' if w > h else 'portrait'

    def _fig_size(self, frame_widget, rows=1):
        """Return (w_in, h_in) for a matplotlib figure that fits frame_widget."""
        self.update_idletasks()
        fw = max(200, frame_widget.winfo_width())
        fh = max(100, frame_widget.winfo_height())
        dpi = 96
        return (fw/dpi - 0.2, (fh/dpi - 0.2) * rows)

    # ════════════════════════════════════════════════════
    # PERSISTENT STATUS BAR — 3 rows × 6 gauges
    # ════════════════════════════════════════════════════
    def _build_statusbar(self):
        sb = tk.Frame(self, bg='#050a0f'); sb.pack(fill=tk.X)
        self._sb = {}
        fsg = self._fsg; fss = self._fs

        rows = [
            [('RPM', 'rpm', RED, '{:.0f}'),
             ('MAP', 'map_kpa', BLUE, '{:.0f}kPa'),
             ('TPS', 'tps', AMBER, '{:.1f}%'),
             ('AFR', 'afr', CYAN, '{:.2f}'),
             ('λ',   'lam', CYAN, '{:.3f}'),
             ('IGN', 'adv', YELL, '{:.1f}°')],
            [('CLT', 'clt', '#ff6666', '{:.0f}°C'),
             ('IAT', 'iat', '#4466ff', '{:.0f}°C'),
             ('PW',  'pw',  '#ff88aa', '{:.2f}ms'),
             ('DC',  'dc',  '#ff88aa', '{:.1f}%'),
             ('EGT', 'egt', '#ff8844', '{:.0f}°C'),
             ('OIL', 'oil', '#88ccff', '{:.0f}psi')],
            [('BAT', 'batt', GREEN,  '{:.2f}V'),
             ('KMH', 'spd',  GREEN,  '{:.0f}'),
             ('GR',  'gear', WHITE,  '{}'),
             ('DWL', 'dwell',AMBER,  '{:.2f}ms'),
             ('STFT','stft', AMBER,  '{:+.1f}%'),
             ('LTFT','ltft', RED,    '{:+.1f}%')],
        ]
        for row_gauges in rows:
            rf = tk.Frame(sb, bg='#050a0f'); rf.pack(fill=tk.X)
            for col, (label, key, color, fmt) in enumerate(row_gauges):
                fr = tk.Frame(rf, bg='#050a0f')
                fr.grid(row=0, column=col, padx=2, pady=1, sticky='ew')
                rf.grid_columnconfigure(col, weight=1)
                tk.Label(fr, text=label, bg='#050a0f', fg=GRAY,
                         font=('Courier', fss, 'bold')).pack()
                var = tk.StringVar(value='--')
                tk.Label(fr, textvariable=var, bg='#050a0f', fg=color,
                         font=('Courier', fsg, 'bold')).pack()
                self._sb[key] = (var, fmt)

        # DTC + scenario strip
        bot = tk.Frame(sb, bg='#0a0505'); bot.pack(fill=tk.X)
        self._dtc_sb = tk.StringVar(value='✓ NO DTCs')
        tk.Label(bot, textvariable=self._dtc_sb, bg='#0a0505', fg=RED,
                 font=('Courier', self._fsl, 'bold'), anchor='w').pack(side=tk.LEFT, padx=6)
        self._sc_var = tk.StringVar(value='WARMUP')
        tk.Label(bot, textvariable=self._sc_var, bg='#0a0505', fg=PURP,
                 font=('Courier', self._fsl, 'bold')).pack(side=tk.RIGHT, padx=8)

    # ════════════════════════════════════════════════════
    # TAB 1 — MECHANIC  (OBD requests + live graph)
    # Portrait:  buttons scrollable top, graph fills rest
    # Landscape: buttons narrow left, graph fills right
    # ════════════════════════════════════════════════════
    def _tab_mechanic(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' MECHANIC ')
        self._mech_f = f

        # ── controls panel (scrollable, orientation-aware)
        self._mech_ctrl = tk.Frame(f, bg=BG)
        self._mech_graph = tk.Frame(f, bg=BG)

        self._mech_result = tk.StringVar(value='Send a request or enable auto-poll')
        self._ap_var = tk.BooleanVar(value=False)
        self._lv = {}

        self._build_mech_ctrl()
        self._place_mech_layout()

    def _build_mech_ctrl(self):
        ctrl = self._mech_ctrl
        for w in ctrl.winfo_children(): w.destroy()

        _, inner = self._scrollframe(ctrl)

        # OBD PIDs
        obd = self._lf(inner, 'OBD-II REQUESTS')
        obd.pack(fill=tk.X, padx=4, pady=4)
        pids = [(0x0C,'RPM'),(0x0D,'Speed'),(0x05,'CLT'),(0x0F,'IAT'),
                (0x0B,'MAP'),(0x11,'TPS'),(0x0E,'Timing'),(0x04,'Load'),
                (0x06,'STFT'),(0x07,'LTFT'),(0x44,'Lambda'),(0x5C,'Oil T')]
        for i, (pid, name) in enumerate(pids):
            r, c = divmod(i, 2)
            self._btn(obd, f'{pid:02X}h  {name}',
                      lambda p=pid: self._obd(p), fg=CYAN).grid(
                      row=r, column=c, padx=3, pady=3, sticky='ew', ipadx=2)
        obd.grid_columnconfigure(0, weight=1); obd.grid_columnconfigure(1, weight=1)

        # DTC / mode controls
        dt = self._lf(inner, 'DTC + INFO')
        dt.pack(fill=tk.X, padx=4, pady=4)
        for text, mode, pid in [
            ('Read Active DTCs', 0x03, None), ('Read Pending', 0x07, None),
            ('Clear All DTCs',   0x04, None), ('Read VIN',    0x09, 0x02),
            ('Freeze Frame',     None, None)]:
            cmd = (lambda m=mode, p=pid: self._obd_raw(m,p)) if mode else self._freeze
            self._btn(dt, text, cmd, fg=AMBER).pack(fill=tk.X, padx=4, pady=2)

        tk.Checkbutton(dt, text='AUTO-POLL (live stream)',
                       variable=self._ap_var, bg=PANEL, fg=CYAN,
                       selectcolor=DARK, font=('Courier', self._fsl, 'bold'),
                       command=lambda: setattr(self.obd,'autopoll',self._ap_var.get()),
                       pady=6).pack(anchor=tk.W, padx=6, pady=4)

        # Live values
        lv = self._lf(inner, 'LIVE VALUES')
        lv.pack(fill=tk.X, padx=4, pady=4)
        params = [('STFT','stft',AMBER,'{:+.1f}%'), ('LTFT','ltft',AMBER,'{:+.1f}%'),
                  ('KNOCK RET','kret',RED,'{:.1f}°'), ('KNOCK LVL','klvl',RED,'{:.2f}'),
                  ('EGO','ego',GREEN,'{}'),           ('VE LIVE','ve_live',GREEN,'{:.1f}%'),
                  ('IGN LIVE','ign_live',YELL,'{:.1f}°'), ('AFR TGT','afr_tgt',CYAN,'{:.2f}'),
                  ('ACCEL ENR','accel',AMBER,'{}')]
        for i, (label, key, color, fmt) in enumerate(params):
            tk.Label(lv, text=f'{label}:', bg=PANEL, fg=GRAY,
                     font=('Courier', self._fs), anchor='e', width=11).grid(
                     row=i, column=0, sticky='e', padx=2, pady=2)
            var = tk.StringVar(value='---')
            tk.Label(lv, textvariable=var, bg=PANEL, fg=color,
                     font=('Courier', self._fsl, 'bold'), anchor='w', width=10).grid(
                     row=i, column=1, sticky='w')
            self._lv[key] = (var, fmt)

        # Result text
        res = self._lf(inner, 'RESULT')
        res.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(res, textvariable=self._mech_result, bg=DARK, fg=CYAN,
                 font=('Courier', self._fs), wraplength=max(200, self.SW//2 - 40),
                 justify=tk.LEFT, anchor='nw').pack(fill=tk.X, padx=4, pady=4)

    def _place_mech_layout(self):
        orient = self._orient()
        self._mech_ctrl.pack_forget()
        self._mech_graph.pack_forget()
        f = self._mech_f

        if orient == 'landscape':
            # Controls narrow left (~32%), graph fills right
            self._mech_ctrl.place(relx=0, rely=0, relwidth=0.32, relheight=1.0)
            self._mech_graph.place(relx=0.32, rely=0, relwidth=0.68, relheight=1.0)
        else:
            # Portrait: controls compact top (~38%), graph below
            self._mech_ctrl.place(relx=0, rely=0, relwidth=1.0, relheight=0.40)
            self._mech_graph.place(relx=0, rely=0.40, relwidth=1.0, relheight=0.60)

        # Build the graph area
        for w in self._mech_graph.winfo_children(): w.destroy()
        if MPL:
            self._mfig = Figure(facecolor=DARK)
            self._mfig.subplots_adjust(left=0.09, right=0.97, hspace=0.55, top=0.92, bottom=0.12)
            self._max1 = self._mfig.add_subplot(211)
            self._max2 = self._mfig.add_subplot(212)
            for ax, title, c in [(self._max1,'AFR',CYAN),(self._max2,'STFT/LTFT %',AMBER)]:
                ax.set_facecolor(DARK); ax.set_title(title, fontsize=9, color=c, pad=3)
                ax.grid(True, color='#1a2535', lw=0.5)
                ax.tick_params(colors=GRAY, labelsize=8)
            self._mcanvas = FigureCanvasTkAgg(self._mfig, master=self._mech_graph)
            self._mcanvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _obd(self, pid):
        r = self.obd.request(0x01, pid); self._mech_result.set(r)
    def _obd_raw(self, mode, pid=None):
        r = self.obd.request(mode, pid); self._mech_result.set(r or 'OK')
    def _freeze(self):
        s = self.eng.snap()
        lines = [f'═ FREEZE  {time.strftime("%H:%M:%S")}  {s["scenario"].upper()} ═']
        for k, label in [('rpm','RPM'),('map_kpa','MAP kPa'),('tps','TPS%'),
                         ('clt','CLT°C'),('iat','IAT°C'),('afr','AFR'),('lam','Lambda'),
                         ('adv','IGN Adv'),('pw','PW ms'),('dc','DC%'),('batt','Batt V'),
                         ('stft','STFT%'),('ltft','LTFT%'),('kret','Knock Ret°'),('egt','EGT°C')]:
            v = s.get(k,'?')
            lines.append(f'  {label:<12} = {round(v,3) if isinstance(v,float) else v}')
        if s['active_dtcs']:
            lines.append('  DTCs:')
            [lines.append(f'    {c} — {d}') for c, d in s['active_dtcs']]
        self._mech_result.set('\n'.join(lines))

    # ════════════════════════════════════════════════════
    # TAB 2 — OSCILLOSCOPE
    # Portrait:  signal selectors top, full-width traces below
    # Landscape: signal selectors left strip, traces fill right
    # ════════════════════════════════════════════════════
    def _tab_scope(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' SCOPE ')
        self._scope_f = f
        self._ch1 = tk.StringVar(value=ScopeGen.SIGS[0])
        self._ch2 = tk.StringVar(value=ScopeGen.SIGS[3])
        self._ch1_en = tk.BooleanVar(value=True)
        self._ch2_en = tk.BooleanVar(value=True)
        self._sinfo  = tk.StringVar(value='')
        self._scope_ctrl  = tk.Frame(f, bg=BG)
        self._scope_graph = tk.Frame(f, bg=BG)
        self._build_scope_ctrl()
        self._place_scope_layout()

    def _build_scope_ctrl(self):
        ctrl = self._scope_ctrl
        for w in ctrl.winfo_children(): w.destroy()
        fs = self._fsl

        for ch_num, var, en_var, color in [
            (1, self._ch1, self._ch1_en, GREEN),
            (2, self._ch2, self._ch2_en, AMBER)]:
            row = tk.Frame(ctrl, bg=PANEL); row.pack(fill=tk.X, padx=4, pady=3)
            tk.Checkbutton(row, text=f'CH{ch_num}', variable=en_var,
                           bg=PANEL, fg=color, selectcolor=DARK,
                           font=('Courier', fs, 'bold')).pack(side=tk.LEFT, padx=4)
            cb = ttk.Combobox(row, textvariable=var, values=ScopeGen.SIGS,
                              font=('Courier', fs), state='readonly')
            cb.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, ipady=4)

        tk.Label(ctrl, textvariable=self._sinfo, bg=BG, fg=CYAN,
                 font=('Courier', self._fs), justify=tk.LEFT).pack(
                 anchor=tk.W, padx=6, pady=4)
        tk.Label(ctrl, text='Scope responds to live engine\nWOT → PW grows, AFR goes rich',
                 bg=BG, fg=DIM, font=('Courier', self._fs), justify=tk.LEFT).pack(
                 anchor=tk.W, padx=6)

    def _place_scope_layout(self):
        orient = self._orient()
        self._scope_ctrl.place_forget()
        self._scope_graph.place_forget()
        f = self._scope_f
        if orient == 'landscape':
            self._scope_ctrl.place(relx=0,    rely=0, relwidth=0.25, relheight=1.0)
            self._scope_graph.place(relx=0.25, rely=0, relwidth=0.75, relheight=1.0)
        else:
            ctrl_h = 0.22
            self._scope_ctrl.place(relx=0, rely=0, relwidth=1.0, relheight=ctrl_h)
            self._scope_graph.place(relx=0, rely=ctrl_h, relwidth=1.0, relheight=1.0-ctrl_h)

        for w in self._scope_graph.winfo_children(): w.destroy()
        if MPL:
            self._sfig = Figure(facecolor='#030810')
            self._sfig.subplots_adjust(left=0.08, right=0.97, hspace=0.42, top=0.95, bottom=0.08)
            self._sax1 = self._sfig.add_subplot(211)
            self._sax2 = self._sfig.add_subplot(212)
            for ax in [self._sax1, self._sax2]:
                ax.set_facecolor('#030810')
                ax.grid(True, color='#081508', lw=0.9)
                ax.tick_params(colors=DIM, labelsize=9)
            self._scanvas = FigureCanvasTkAgg(self._sfig, master=self._scope_graph)
            self._scanvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ════════════════════════════════════════════════════
    # TAB 3 — CAN BUS (J1939 + OBD-II)
    # ════════════════════════════════════════════════════
    def _tab_can(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' CAN BUS ')

        info = self._lf(f, 'J1939 29-bit Frame')
        info.pack(fill=tk.X, padx=4, pady=4)
        t = tk.Text(info, height=3, bg=DARK, fg='#aaccff',
                    font=('Courier', self._fs), relief='flat', wrap='none')
        t.pack(fill=tk.X, padx=3, pady=3)
        t.insert('1.0',
            '29-bit ID: [28..26]=Priority [23..8]=PGN [7..0]=SA\n'
            'EEC1: Priority=3 PGN=0xF004(61444) SA=0x00  → 0x0CF00400\n'
            'EEC2:61443 ET1:65262 CCVS:65265 DM1:65226 EFL/P1:65263')
        t.config(state='disabled')

        nb2 = ttk.Notebook(f); nb2.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # J1939
        jf = ttk.Frame(nb2); nb2.add(jf, text=' J1939 ')
        jf2 = tk.Frame(jf, bg=BG); jf2.pack(fill=tk.BOTH, expand=True)
        cols = ('Time','CAN ID','PGN','PGN Name','SA','Data','Decoded')
        self._j_tv = ttk.Treeview(jf2, columns=cols, show='headings', height=12)
        for col, w in zip(cols, [70,110,55,150,80,200,300]):
            self._j_tv.heading(col, text=col); self._j_tv.column(col, width=w, anchor=tk.W)
        jy = ttk.Scrollbar(jf2, orient=tk.VERTICAL,   command=self._j_tv.yview)
        jx = ttk.Scrollbar(jf2, orient=tk.HORIZONTAL, command=self._j_tv.xview)
        self._j_tv.config(yscrollcommand=jy.set, xscrollcommand=jx.set)
        self._j_tv.grid(row=0, column=0, sticky='nsew')
        jy.grid(row=0, column=1, sticky='ns'); jx.grid(row=1, column=0, sticky='ew')
        jf2.grid_rowconfigure(0, weight=1); jf2.grid_columnconfigure(0, weight=1)

        # OBD-II
        of = ttk.Frame(nb2); nb2.add(of, text=' OBD-II ')
        of2 = tk.Frame(of, bg=BG); of2.pack(fill=tk.BOTH, expand=True)
        cols2 = ('Time','ID','Dir','Data','Decoded')
        self._obd_can_tv = ttk.Treeview(of2, columns=cols2, show='headings', height=12)
        for col, w in zip(cols2, [70,70,42,220,450]):
            self._obd_can_tv.heading(col, text=col); self._obd_can_tv.column(col, width=w, anchor=tk.W)
        oy = ttk.Scrollbar(of2, orient=tk.VERTICAL,   command=self._obd_can_tv.yview)
        ox = ttk.Scrollbar(of2, orient=tk.HORIZONTAL, command=self._obd_can_tv.xview)
        self._obd_can_tv.config(yscrollcommand=oy.set, xscrollcommand=ox.set)
        self._obd_can_tv.grid(row=0, column=0, sticky='nsew')
        oy.grid(row=0, column=1, sticky='ns'); ox.grid(row=1, column=0, sticky='ew')
        of2.grid_rowconfigure(0, weight=1); of2.grid_columnconfigure(0, weight=1)

        self._obd_tv = self._obd_can_tv  # mechanic tab also updates this

    # ════════════════════════════════════════════════════
    # TAB 4 — ECU TUNING
    # ════════════════════════════════════════════════════
    def _tab_tuning(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' TUNING ')
        self._connected = False

        top = tk.Frame(f, bg=BG); top.pack(fill=tk.X, padx=4, pady=4)

        # Connection
        conn = self._lf(top, 'ECU CONNECTION')
        conn.pack(side=tk.LEFT, fill=tk.Y, padx=4)
        self._conn_v = tk.StringVar(value='DISCONNECTED')
        self._conn_l = tk.Label(conn, textvariable=self._conn_v, bg='#1a0000', fg=RED,
                                font=('Courier', self._fsl, 'bold'), width=13)
        self._conn_l.pack(pady=4, padx=4)
        for text, cmd, col in [
            ('Connect',  self._ecu_conn,   GREEN),
            ('Disconnect',self._ecu_disc,  GRAY),
            ('Burn Flash',self._burn,      RED),
            ('Revert',    self._revert,    AMBER),
            ('Export CSV',self._export_csv,CYAN)]:
            self._btn(conn, text, cmd, fg=col).pack(fill=tk.X, padx=4, pady=2)

        # Operating point
        op = self._lf(top, 'LIVE OPERATING POINT')
        op.pack(side=tk.LEFT, fill=tk.Y, padx=4)
        self._op = {}
        for i, (label, key, color, fmt) in enumerate([
            ('RPM','rpm',RED,'{:.0f}'), ('MAP kPa','map_kpa',BLUE,'{:.0f}'),
            ('VE live','ve_live',GREEN,'{:.1f}%'), ('IGN live','ign_live',YELL,'{:.1f}°'),
            ('AFR tgt','afr_tgt',CYAN,'{:.2f}'),   ('AFR act','afr',CYAN,'{:.2f}'),
            ('STFT','stft',AMBER,'{:+.1f}%'),       ('LTFT','ltft',AMBER,'{:+.1f}%'),
            ('Inj PW','pw','#ff88aa','{:.2f}ms'),   ('Inj DC','dc','#ff88aa','{:.1f}%'),
            ('Knock Ret','kret',RED,'{:.1f}°')]):
            tk.Label(op, text=f'{label}:', bg=PANEL, fg=GRAY,
                     font=('Courier', self._fs), anchor='e', width=11).grid(
                     row=i, column=0, sticky='e', padx=2, pady=2)
            var = tk.StringVar(value='---')
            tk.Label(op, textvariable=var, bg=PANEL, fg=color,
                     font=('Courier', self._fsl, 'bold'), width=10).grid(
                     row=i, column=1, sticky='w')
            self._op[key] = (var, fmt)

        # Map tabs
        mnb = ttk.Notebook(f); mnb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._ve_ed  = self._maptab(mnb, ' VE Table (%) ', 've_table',  '%',  20, 108)
        self._ig_ed  = self._maptab(mnb, ' IGN Adv (°) ', 'ign_table', '°',   0,  42)
        self._afr_ed = self._maptab(mnb, ' AFR Target  ', 'afr_table', ':1', 11,  17)

    def _maptab(self, nb, label, attr, unit, vmin, vmax):
        frm = ttk.Frame(nb); nb.add(frm, text=label)
        # Wrap map editor in a scrollable canvas (map is wide on portrait)
        outer = tk.Frame(frm, bg=BG); outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        hsc = ttk.Scrollbar(outer, orient=tk.HORIZONTAL, command=canvas.xview)
        vsc = ttk.Scrollbar(outer, orient=tk.VERTICAL,   command=canvas.yview)
        canvas.configure(xscrollcommand=hsc.set, yscrollcommand=vsc.set)
        hsc.pack(side=tk.BOTTOM, fill=tk.X)
        vsc.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0,0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        ed = MapEditor(inner, self.maps, attr, label.strip(), unit, vmin, vmax)
        ed.pack(padx=4, pady=4)
        self._btn(frm, '  View 3D Surface  ', ed.show3d, fg=CYAN).pack(pady=4)
        return ed

    def _ecu_conn(self):
        self._connected = True; self._conn_v.set('CONNECTED')
        self._conn_l.config(bg='#001a00', fg=GREEN)
    def _ecu_disc(self):
        self._connected = False; self._conn_v.set('DISCONNECTED')
        self._conn_l.config(bg='#1a0000', fg=RED)
    def _burn(self):
        if not self._connected: messagebox.showerror('Error','Connect first'); return
        messagebox.showinfo('Flash','Maps burned — CRC32 verified')
    def _revert(self): messagebox.showinfo('Revert','Backup maps restored')
    def _export_csv(self):
        lines = []
        for name, attr in [('VE','ve_table'),('IGN','ign_table'),('AFR','afr_table')]:
            lines.append(f'# {name}')
            lines.append('MAP/RPM,'+','.join(str(r) for r in ECUMaps.RPM_BINS))
            for mi, row in enumerate(getattr(self.maps, attr)):
                lines.append(str(ECUMaps.MAP_BINS[mi])+','+','.join(str(v) for v in row))
            lines.append('')
        path = '/sdcard/Download/ck_maps.csv'
        open(path, 'w').write('\n'.join(lines))
        messagebox.showinfo('Export', f'Saved to {path}')

    # ════════════════════════════════════════════════════
    # TAB 5 — CORRECTIONS
    # ════════════════════════════════════════════════════
    def _tab_corrections(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' CORR ')
        _, inner = self._scrollframe(f)
        fs = self._fs

        def corr_row(title, xs, ys, color):
            lf = self._lf(inner, title); lf.pack(fill=tk.X, padx=5, pady=4)
            hdr = tk.Frame(lf, bg=PANEL); hdr.pack(padx=4, pady=3)
            for i, x in enumerate(xs):
                tk.Label(hdr, text=str(x), bg=PANEL, fg='#88aacc',
                         font=('Courier', fs), width=5).grid(row=0, column=i+1)
            for i, y in enumerate(ys):
                e = tk.Entry(hdr, width=5, font=('Courier', fs),
                             justify='center', bg=DARK, fg=color)
                e.insert(0, str(y)); e.grid(row=1, column=i+1, padx=1)

        corr_row('CLT Fuel Correction (%)  100=no change',
                 self.maps.clt_ax, self.maps.clt_corr, BLUE)
        corr_row('IAT Fuel Correction (%)  hot air=less fuel',
                 self.maps.iat_ax, self.maps.iat_corr, CYAN)
        corr_row('Injector Dead Time vs Battery (ms)',
                 self.maps.dt_v, self.maps.dt_ms, AMBER)
        corr_row('Idle RPM Target vs CLT',
                 self.maps.idle_cax, self.maps.idle_rpm, GREEN)

        cf = self._lf(inner, 'GLOBAL ECU CONFIG')
        cf.pack(fill=tk.X, padx=5, pady=6)
        gr = tk.Frame(cf, bg=PANEL); gr.pack(padx=4, pady=4)
        self._cfg = {}
        params = [('req_fuel','Base Req Fuel ms'), ('soft_cut','Soft Rev Limit'),
                  ('hard_cut','Hard Rev Limit'),   ('accel_mult','Accel Mult x'),
                  ('accel_dur','Accel Duration ms'),('knock_step','Knock Step °'),
                  ('knock_max','Knock Max °'),      ('fuel_psi','Fuel Pres psi')]
        for i, (attr, label) in enumerate(params):
            r, c = divmod(i, 2)
            tk.Label(gr, text=label, bg=PANEL, fg=GRAY,
                     font=('Courier', fs)).grid(row=r*2, column=c, padx=8, pady=1)
            e = tk.Entry(gr, width=8, font=('Courier', self._fsl),
                         justify='center', bg=DARK, fg=AMBER)
            e.insert(0, str(getattr(self.maps, attr, 0)))
            e.grid(row=r*2+1, column=c, padx=8, pady=2)
            self._cfg[attr] = e
        self._btn(cf, 'Apply Config', self._apply_cfg, fg=GREEN).pack(pady=6, padx=20, fill=tk.X)

    def _apply_cfg(self):
        for attr, e in self._cfg.items():
            try: setattr(self.maps, attr, float(e.get()))
            except: pass
        messagebox.showinfo('Config', 'Applied to running engine')

    # ════════════════════════════════════════════════════
    # TAB 6 — SENSORS
    # Portrait: 2-column grid + graphs
    # Landscape: 4-column grid + graphs side by side
    # ════════════════════════════════════════════════════
    def _tab_sensors(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' SENSORS ')
        self._sensor_f = f
        self._sv = {}

        sensors = [
            ('Wideband O2', 'afr',  CYAN,      'AEM/Innovate  AFR :1'),
            ('Lambda',      'lam',  CYAN,      '1.000=stoich  0.85=WOT'),
            ('EGT Ch1',     'egt',  '#ff8844', 'K-type MAX6675  °C'),
            ('Coolant Temp','clt',  BLUE,      'NTC 2252Ω  °C'),
            ('Inlet Air',   'iat',  '#4466ff', 'IAT correction table'),
            ('Oil Pressure','oil',  '#88ccff', '0-100psi piezo  psi'),
            ('Battery',     'batt', GREEN,     'Dead time table V'),
            ('Inj DC',      'dc',   '#ff88aa', 'Above 85% = maxed  %'),
            ('Inj PW',      'pw',   '#ff88aa', 'ms per cycle'),
            ('Vehicle Spd', 'spd',  GREEN,     'Hall sensor km/h'),
        ]

        # Sensor tile grid — 2 cols portrait / 4 cols landscape
        orient = self._orient()
        cols = 2 if orient == 'portrait' else 4
        top = tk.Frame(f, bg=BG); top.pack(fill=tk.X, padx=4, pady=4)

        for i, (name, key, color, tip) in enumerate(sensors):
            r, c = divmod(i, cols)
            fr = tk.Frame(top, bg=DARK, relief='ridge', bd=2)
            fr.grid(row=r, column=c, padx=4, pady=4, ipadx=8, ipady=6, sticky='nsew')
            top.grid_columnconfigure(c, weight=1)
            tk.Label(fr, text=name,  bg=DARK, fg=GRAY,
                     font=('Courier', self._fs, 'bold')).pack()
            var = tk.StringVar(value='---')
            tk.Label(fr, textvariable=var, bg=DARK, fg=color,
                     font=('Courier', self._fsg, 'bold')).pack()
            tk.Label(fr, text=tip, bg=DARK, fg=DIM,
                     font=('Courier', max(7,self._fs-2)), wraplength=160).pack()
            self._sv[key] = var

        # Sensor graphs
        if MPL:
            gf = self._lf(f, 'Fuel Trims / EGT / AFR History')
            gf.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            self._tfig = Figure(facecolor=DARK)
            self._tfig.subplots_adjust(left=0.08, right=0.97, hspace=0.55,
                                        wspace=0.35, top=0.9, bottom=0.12)
            self._tax1 = self._tfig.add_subplot(131)
            self._tax2 = self._tfig.add_subplot(132)
            self._tax3 = self._tfig.add_subplot(133)
            for ax, t, c in [(self._tax1,'Fuel Trims %',AMBER),
                              (self._tax2,'EGT °C','#ff8844'),
                              (self._tax3,'AFR',CYAN)]:
                ax.set_facecolor(DARK); ax.set_title(t, fontsize=9, color=c, pad=3)
                ax.grid(True, color='#1a2535', lw=0.5)
                ax.tick_params(colors=GRAY, labelsize=8)
            self._tcanvas = FigureCanvasTkAgg(self._tfig, master=gf)
            self._tcanvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ════════════════════════════════════════════════════
    # TAB 7 — DATALOGGER
    # ════════════════════════════════════════════════════
    def _tab_datalog(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' DATALOG ')
        ctrl = tk.Frame(f, bg=BG); ctrl.pack(fill=tk.X, padx=4, pady=4)
        self._log_on = False; self._log_rows = []
        self._log_v  = tk.StringVar(value='LOGGING: OFF')
        tk.Label(ctrl, textvariable=self._log_v, bg=DARK, fg=RED,
                 font=('Courier', self._fsl, 'bold'), width=20).pack(side=tk.LEFT, padx=6)
        for text, cmd, col in [
            ('▶ Start', self._log_start, GREEN), ('■ Stop', self._log_stop,  RED),
            ('Save CSV', self._log_save, AMBER),  ('Clear',  self._log_clear, GRAY)]:
            self._btn(ctrl, text, cmd, fg=col).pack(side=tk.LEFT, padx=4)
        tk.Label(ctrl, text='5Hz  all params  CSV export',
                 bg=BG, fg=DIM, font=('Courier', self._fs)).pack(side=tk.LEFT, padx=8)

        cols = ('Time','RPM','MAP','TPS','CLT','IAT','AFR','λ',
                'IGN','STFT','LTFT','PW','DC','Knock','EGT','Gear','Scenario')
        tv_f = tk.Frame(f, bg=BG); tv_f.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        tv_f.grid_rowconfigure(0, weight=1); tv_f.grid_columnconfigure(0, weight=1)
        self._log_tv = ttk.Treeview(tv_f, columns=cols, show='headings', height=20)
        for col, w in zip(cols, [66,60,54,50,50,50,54,54,50,54,54,54,50,54,54,44,75]):
            self._log_tv.heading(col, text=col); self._log_tv.column(col, width=w, anchor=tk.CENTER)
        ysc = ttk.Scrollbar(tv_f, orient=tk.VERTICAL,   command=self._log_tv.yview)
        xsc = ttk.Scrollbar(tv_f, orient=tk.HORIZONTAL, command=self._log_tv.xview)
        self._log_tv.config(yscrollcommand=ysc.set, xscrollcommand=xsc.set)
        self._log_tv.grid(row=0, column=0, sticky='nsew')
        ysc.grid(row=0, column=1, sticky='ns')
        xsc.grid(row=1, column=0, sticky='ew')

    def _log_start(self): self._log_on=True;  self._log_v.set('LOGGING: ON  ●')
    def _log_stop(self):  self._log_on=False; self._log_v.set(f'STOPPED ({len(self._log_rows)} rows)')
    def _log_clear(self):
        self._log_rows.clear()
        for i in self._log_tv.get_children(): self._log_tv.delete(i)
    def _log_save(self):
        if not self._log_rows: messagebox.showinfo('Log','No data'); return
        path = '/sdcard/Download/ck_datalog.csv'
        hdr = 'time,rpm,map,tps,clt,iat,afr,lambda,ign,stft,ltft,pw,dc,knock,egt,gear,scenario'
        open(path,'w').write(hdr+'\n'+'\n'.join(','.join(str(v) for v in r) for r in self._log_rows))
        messagebox.showinfo('Saved', f'{path}\n{len(self._log_rows)} rows')

    # ════════════════════════════════════════════════════
    # TAB 8 — FAULT INJECTION
    # ════════════════════════════════════════════════════
    def _tab_faults(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text=' FAULTS ')
        _, inner = self._scrollframe(f)

        tk.Label(inner, text='FAULT INJECTION — simulate real failure modes',
                 bg=BG, fg=RED, font=('Courier', self._fsl, 'bold')).pack(pady=6)
        tk.Label(inner, text='Watch DTC strip at top, fuel trims and AFR respond in real-time',
                 bg=BG, fg=GRAY, font=('Courier', self._fs)).pack()

        self._fault_vars = {}
        faults = [
            ('fault_o2_dead',   'O2 SENSOR DEAD',
             'ECU goes open-loop\nP0131 sets\nSTFT/LTFT stop learning', RED),
            ('fault_map_stuck', 'MAP STUCK @ 50kPa',
             'Wrong fueling all loads\nAFR swings rich/lean\nP0106 on real ECU', AMBER),
            ('fault_clt_short', 'CLT SHORTED TO GND',
             'Reads -40°C constantly\n180% cold fuel correction\nP0117 sets', BLUE),
            ('fault_lean_vac',  'VACUUM LEAK',
             'Unmetered air added\nLTFT goes positive\nP0171 if severe', CYAN),
            ('fault_ign_retard','TIMING RETARD -10°',
             'Bad knock sensor / worn chain\nPower loss rich exhaust\nBase timing degraded', YELL),
            ('fault_inj_stuck', 'INJECTOR STUCK OPEN',
             'AFR 10-11:1 very rich\nP0201 sets\nDC shows 100%', PURP),
        ]
        orient = self._orient()
        gcols = 2 if orient == 'landscape' else 1
        grid = tk.Frame(inner, bg=BG); grid.pack(padx=12, pady=8, fill=tk.X)
        for i, (attr, title, desc, color) in enumerate(faults):
            r, c = divmod(i, gcols)
            fr = tk.Frame(grid, bg=PANEL, relief='ridge', bd=2)
            fr.grid(row=r, column=c, padx=8, pady=6, sticky='ew', ipadx=10, ipady=8)
            grid.grid_columnconfigure(c, weight=1)
            var = tk.BooleanVar(value=False)
            self._fault_vars[attr] = var
            tk.Checkbutton(fr, text=title, variable=var, bg=PANEL, fg=color,
                           selectcolor=DARK, font=('Courier', self._fsl, 'bold'),
                           pady=4,
                           command=lambda a=attr, v=var: setattr(self.eng, a, v.get())).pack(anchor=tk.W)
            tk.Label(fr, text=desc, bg=PANEL, fg=DIM,
                     font=('Courier', self._fs), justify=tk.LEFT).pack(anchor=tk.W, padx=8, pady=2)

        # Misfire
        mf = self._lf(inner, 'MISFIRE CYLINDER')
        mf.pack(fill=tk.X, padx=12, pady=6)
        mfi = tk.Frame(mf, bg=PANEL); mfi.pack(padx=6, pady=6)
        self._miss_v = tk.IntVar(value=0)
        for cyl, label in [(0,'None'),(1,'Cyl 1'),(2,'Cyl 2'),(3,'Cyl 3'),(4,'Cyl 4')]:
            tk.Radiobutton(mfi, text=label, variable=self._miss_v, value=cyl,
                           bg=PANEL, fg=RED, selectcolor=DARK,
                           font=('Courier', self._fsl, 'bold'), pady=6,
                           command=lambda: setattr(self.eng,'fault_miss_cyl',self._miss_v.get())).pack(
                           side=tk.LEFT, padx=10)
        tk.Label(mf, text='Misfire → knock activity, rough idle, P030x DTC',
                 bg=PANEL, fg=DIM, font=('Courier', self._fs)).pack(pady=2)

        self._btn(inner, 'CLEAR ALL FAULTS', self._clear_faults, fg=RED, bg='#3a0000').pack(
            pady=12, padx=20, fill=tk.X)

    def _clear_faults(self):
        for attr, var in self._fault_vars.items():
            var.set(False); setattr(self.eng, attr, False)
        self._miss_v.set(0); self.eng.fault_miss_cyl = 0
        messagebox.showinfo('Faults', 'All faults cleared')

    # ════════════════════════════════════════════════════
    # ORIENTATION CHANGE HANDLER
    # ════════════════════════════════════════════════════
    def _on_resize(self, event):
        if event.widget is not self: return
        orient = self._orient()
        if orient == self._last_orient: return
        self._last_orient = orient
        # Rebuild the orientation-sensitive tab layouts
        self._place_mech_layout()
        self._place_scope_layout()

    # ════════════════════════════════════════════════════
    # MASTER TICK — 350ms
    # ════════════════════════════════════════════════════
    def _tick(self):
        s = self.eng.snap()

        # histories
        for k, sk in [('afr','afr'),('rpm','rpm'),('knock','klvl'),
                       ('stft','stft'),('ltft','ltft'),('egt','egt'),
                       ('oil','oil'),('tps','tps'),('adv','adv')]:
            self._H[k].append(s[sk])

        # ── STATUS BAR
        sb_map = {
            'rpm':(s['rpm'],'{:.0f}'),     'map_kpa':(s['map_kpa'],'{:.0f}kPa'),
            'tps':(s['tps'],'{:.1f}%'),    'afr':(s['afr'],'{:.2f}'),
            'lam':(s['lam'],'{:.3f}'),     'adv':(s['adv'],'{:.1f}°'),
            'clt':(s['clt'],'{:.0f}°C'),   'iat':(s['iat'],'{:.0f}°C'),
            'pw':(s['pw'],'{:.2f}ms'),      'dc':(s['dc'],'{:.1f}%'),
            'egt':(s['egt'],'{:.0f}°C'),    'oil':(s['oil'],'{:.0f}psi'),
            'batt':(s['batt'],'{:.2f}V'),   'spd':(s['spd'],'{:.0f}'),
            'gear':(s['gear'],'{}'),        'dwell':(s['dwell'],'{:.2f}ms'),
            'stft':(s['stft'],'{:+.1f}%'), 'ltft':(s['ltft'],'{:+.1f}%'),
        }
        for key, (val, fmt) in sb_map.items():
            if key in self._sb:
                self._sb[key][0].set(fmt.format(val))
        dtcs = s['active_dtcs']
        self._dtc_sb.set('  DTCs: '+' | '.join(c for c,d in dtcs) if dtcs else '  ✓ NO DTCs')
        self._sc_var.set(s['scenario'].upper())

        # ── MECHANIC tab
        if hasattr(self, '_lv'):
            for k, (var, fmt) in self._lv.items():
                val = s.get(k, '?')
                var.set(fmt.format(val) if isinstance(val,(int,float)) else str(val))
        if MPL and hasattr(self, '_mfig'):
            for ax in [self._max1, self._max2]: ax.clear()
            x = list(range(len(self._H['afr'])))
            self._max1.plot(x, list(self._H['afr']),  color=CYAN, lw=1.5)
            self._max1.axhline(14.7, color=WHITE, lw=0.8, linestyle='--')
            self._max1.set_facecolor(DARK)
            self._max1.set_title('AFR', fontsize=9, color=CYAN, pad=3)
            self._max1.grid(True, color='#1a2535', lw=0.5)
            self._max1.tick_params(colors=GRAY, labelsize=8)
            self._max2.plot(x, list(self._H['stft']), color=AMBER, lw=1.5, label='STFT')
            self._max2.plot(x, [s['ltft']]*len(x),    color=RED,   lw=1.5, linestyle='--', label='LTFT')
            self._max2.axhline(0, color=DIM, lw=0.8)
            self._max2.set_facecolor(DARK)
            self._max2.set_title('STFT / LTFT %', fontsize=9, color=AMBER, pad=3)
            self._max2.grid(True, color='#1a2535', lw=0.5)
            self._max2.tick_params(colors=GRAY, labelsize=8)
            self._max2.legend(fontsize=7, labelcolor=WHITE, loc='upper left')
            self._mfig.tight_layout(pad=0.6)
            self._mcanvas.draw()

        # ── OBD bus
        if hasattr(self, '_obd_can_tv'):
            for i in self._obd_can_tv.get_children(): self._obd_can_tv.delete(i)
            for m in list(self.obd.msgs)[-25:]:
                ts = time.strftime('%H:%M:%S', time.localtime(m['ts']))
                self._obd_can_tv.insert('','end', values=(ts,m['id'],m['dir'],m['data'],m['dec']))

        # ── J1939
        if hasattr(self, '_j_tv'):
            for i in self._j_tv.get_children(): self._j_tv.delete(i)
            for m in list(self.j1939.msgs)[-35:]:
                ts = time.strftime('%H:%M:%S', time.localtime(m['ts']))
                self._j_tv.insert('','end', values=(ts,m['cid'],m['pgn'],m['name'],m['sa'],m['data'],m['dec']))

        # ── SCOPE
        if MPL and hasattr(self, '_sfig'):
            scope_pairs = [(GREEN, self._sax1, self._ch1_en, self._ch1),
                           (AMBER, self._sax2, self._ch2_en, self._ch2)]
            for color, ax, en, cb in scope_pairs:
                ax.clear(); ax.set_facecolor('#030810')
                ax.grid(True, color='#081508', lw=0.9)
                ax.tick_params(colors=DIM, labelsize=9)
                if en.get():
                    res = self.scope.get(cb.get(), s)
                    if res:
                        t, y, ylabel, ymin, ymax = res
                        ax.plot(t*1000, y, color=color, lw=1.5)
                        ax.set_ylabel(ylabel, fontsize=9, color=color)
                        ax.set_ylim(ymin, ymax)
                        ax.set_xlabel('ms', fontsize=8, color=DIM)
            self._sinfo.set(
                f"RPM {s['rpm']:.0f}  PW {s['pw']:.2f}ms\n"
                f"DC {s['dc']:.1f}%  Adv {s['adv']:.1f}°\n"
                f"{s['scenario'].upper()}")
            self._sfig.tight_layout(pad=0.6)
            self._scanvas.draw()

        # ── TUNING op-point
        if hasattr(self, '_op'):
            op_map = {'rpm':s['rpm'],'map_kpa':s['map_kpa'],'ve_live':s['ve_live'],
                      'ign_live':s['ign_live'],'afr_tgt':s['afr_tgt'],'afr':s['afr'],
                      'stft':s['stft'],'ltft':s['ltft'],'pw':s['pw'],'dc':s['dc'],'kret':s['kret']}
            for key, (var, fmt) in self._op.items():
                if key in op_map: var.set(fmt.format(op_map[key]))
            self._ve_ed.cursor(s['rpm'], s['map_kpa'])
            self._ig_ed.cursor(s['rpm'], s['map_kpa'])
            self._afr_ed.cursor(s['rpm'], s['map_kpa'])

        # ── SENSORS
        if hasattr(self, '_sv'):
            sv_map = {'afr':s['afr'],'lam':s['lam'],'egt':s['egt'],
                      'clt':s['clt'],'iat':s['iat'],'oil':s['oil'],
                      'batt':s['batt'],'dc':s['dc'],'pw':s['pw'],'spd':s['spd']}
            for k, var in self._sv.items():
                val = sv_map.get(k, '?')
                var.set(f'{val:.2f}' if isinstance(val, float) else str(val))
        if MPL and hasattr(self, '_tax1'):
            for ax in [self._tax1, self._tax2, self._tax3]:
                ax.clear(); ax.set_facecolor(DARK)
                ax.grid(True, color='#1a2535', lw=0.5)
                ax.tick_params(colors=GRAY, labelsize=8)
            x = list(range(len(self._H['stft'])))
            self._tax1.plot(x, list(self._H['stft']), color=AMBER, lw=1.5, label='STFT')
            self._tax1.plot(x, [s['ltft']]*len(x),    color=RED,   lw=1.5, linestyle='--', label='LTFT')
            self._tax1.axhline(0, color=DIM, lw=0.8)
            self._tax1.axhline(10, color=RED, lw=0.6, linestyle=':')
            self._tax1.axhline(-10, color=BLUE, lw=0.6, linestyle=':')
            self._tax1.set_ylim(-28, 28)
            self._tax1.set_title('Fuel Trims %', fontsize=9, color=AMBER, pad=3)
            self._tax1.legend(fontsize=7, labelcolor=WHITE)
            self._tax2.plot(x, list(self._H['egt']), color='#ff8844', lw=1.5)
            self._tax2.set_title('EGT °C', fontsize=9, color='#ff8844', pad=3)
            self._tax3.plot(x, list(self._H['afr']), color=CYAN, lw=1.5)
            self._tax3.axhline(14.7, color=WHITE, lw=0.8, linestyle='--')
            self._tax3.set_title('AFR', fontsize=9, color=CYAN, pad=3)
            self._tfig.tight_layout(pad=0.5)
            self._tcanvas.draw()

        # ── DATALOG
        if self._log_on:
            row = (time.strftime('%H:%M:%S'),
                   f"{s['rpm']:.0f}", f"{s['map_kpa']:.0f}", f"{s['tps']:.1f}",
                   f"{s['clt']:.0f}", f"{s['iat']:.0f}",     f"{s['afr']:.2f}",
                   f"{s['lam']:.3f}", f"{s['adv']:.1f}",
                   f"{s['stft']:+.1f}", f"{s['ltft']:+.1f}",
                   f"{s['pw']:.2f}",  f"{s['dc']:.1f}",      f"{s['klvl']:.2f}",
                   f"{s['egt']:.0f}", str(s['gear']),         s['scenario'])
            self._log_rows.append(row)
            self._log_tv.insert('', 'end', values=row)
            children = self._log_tv.get_children()
            if len(children) > 500: self._log_tv.delete(children[0])
            self._log_tv.yview_moveto(1)

        self.after(350, self._tick)


if __name__ == '__main__':
    app = CyberKnife()
    app.mainloop()
