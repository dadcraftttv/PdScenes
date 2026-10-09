package app.pdscenes;
import java.util.*;
import android.content.Context;
public class W {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static void walk(double from,double to,double hz,float amp){ for(double t=from;t<to;t+=0.02){ float bump=amp*(float)Math.max(0,Math.sin(2*Math.PI*hz*t)); StepDetector.onAcceleration(0,0,9.80665f+bump,t); } }
  public static void main(String[] a){
    // ---- step detector ----
    StepDetector.reset(); walk(0,6,1.8,4f);
    check(StepDetector.walking(6),"walking signal is detected");
    check(Math.abs(StepDetector.stepsPerSecond(6)-1.8f)<0.5f,"step rate about 1.8/s: "+StepDetector.stepsPerSecond(6));
    check(!StepDetector.walking(12),"stops being 'walking' a few seconds after the last step");
    StepDetector.reset(); for(double t=0;t<6;t+=0.02) StepDetector.onAcceleration(0.05f,0.02f,9.80665f+0.05f*(float)Math.sin(t*3),t);
    check(!StepDetector.walking(6),"phone resting on a table is not walking");
    StepDetector.reset(); walk(0,6,0.3,4f);
    check(!StepDetector.walking(6),"slow sway (0.3 Hz) is not walking");
    StepDetector.reset(); walk(0,6,8,6f);
    check(!StepDetector.walking(6)||StepDetector.stepsPerSecond(6)<=3.6f,"step rate is capped near 3.5/s");
    // fidgeting or shaking the phone while sitting: jolts at irregular times, no steady rhythm
    { Random r=new Random(7); List<Double> g2=new ArrayList<>(); StepDetector.setListener((i,st)->g2.add(i)); StepDetector.reset();
      double last=-1, next=0.3, amp=0; for(double t=0;t<10;t+=0.005){
        if(t>=next){ last=t; amp=(r.nextDouble()-0.5)*16; next=t+0.08+r.nextDouble()*0.9; }   // a jolt, then a random gap
        float bump=(float)(amp*Math.exp(-(t-last)*12));
        StepDetector.onAcceleration(bump*0.5f,bump*0.3f,9.80665f+bump,t); }
      StepDetector.setListener(null);
      check(!StepDetector.walking(10)&&g2.size()<=3,"shaking the phone while sitting is not walking ("+g2.size()+" steps sent)"); }
    // listener gets one call per step with the gap to the previous one
    List<Double> gaps=new ArrayList<>(); StepDetector.setListener((i,st)->gaps.add(i));
    StepDetector.reset(); walk(0,5,2.0,4f); StepDetector.setListener(null);
    double avg=0; for(int i=1;i<gaps.size();i++) avg+=gaps.get(i); avg/=Math.max(1,gaps.size()-1);
    check(gaps.size()>=7&&gaps.size()<=10&&Math.abs(avg-0.5)<0.05&&Math.abs(gaps.get(0)-0.5)<0.05,"step listener: "+gaps.size()+" calls (the first two steps of a walk are held back), gaps about 0.5 s (avg "+avg+")");
    gaps.clear(); StepDetector.setListener((i,st)->gaps.add(i)); StepDetector.reset(); walk(0,0.9,1.8,4f); StepDetector.setListener(null);
    check(gaps.isEmpty(),"two stray bumps do not play drums: "+gaps.size());
    // step strength: harder steps than usual read above 0.5, softer below, ordinary ones near 0.5
    { List<Float> st=new ArrayList<>(); StepDetector.setListener((i,x)->st.add(x)); StepDetector.reset();
      walk(0,6,1.8,4f); float usual=st.get(st.size()-1); st.clear();
      walk(6,8,1.8,7f); float hard=st.get(st.size()-1); st.clear();
      walk(8,14,1.8,4f); walk(14,16,1.8,2.4f); float soft=st.get(st.size()-1); StepDetector.setListener(null);
      check(Math.abs(usual-0.5f)<0.08f&&hard>0.75f&&soft<0.3f,"step strength: usual "+usual+", stomping "+hard+", soft "+soft); }
    // groove: half a minute of steady steps turns it on; a stumble starts the count over; a pause ends it
    { StepDetector.setListener(null); StepDetector.reset(); walk(0,20,1.8,4f); boolean early=StepDetector.grooving();
      walk(20,36,1.8,4f); boolean on=StepDetector.grooving();
      for(double t=36;t<36.6;t+=0.02) StepDetector.onAcceleration(0,0,9.80665f+(t<36.05?6f:0f),t);   // an odd extra bump
      walk(36.6,40,1.8,4f); boolean afterStumble=StepDetector.grooving();
      walk(45,52,1.8,4f); boolean afterPause=StepDetector.grooving();
      check(!early&&on&&!afterStumble&&!afterPause,"groove: off at 20 s, on after 36 s of steady steps, off after a stumble and after a pause ("+early+" "+on+" "+afterStumble+" "+afterPause+")"); }
    // extra bumps: a scuff a third of a step after each step is skipped, so the drums keep the walk's rhythm
    { List<Double> g3=new ArrayList<>(); StepDetector.setListener((i,x)->g3.add(i)); StepDetector.reset();
      for(double t=0;t<10;t+=0.005){ double ph=(t%0.6)/0.6; float bump=(ph<0.12?4f:0f)+(t>3&&ph>0.6&&ph<0.67?4f:0f);
        StepDetector.onAcceleration(0,0,9.80665f+bump,t); }
      StepDetector.setListener(null); int late=0; boolean even=true; for(int i=0;i<g3.size();i++){ if(Math.abs(g3.get(i)-0.6)>0.05) even=false; }
      check(even&&g3.size()>=13,"extra bumps between steps are skipped: "+g3.size()+" steps, gaps "+g3); }
    // speeding up to a jog (bumps exactly between the old steps) is followed after a step or two
    { List<Double> g4=new ArrayList<>(); StepDetector.setListener((i,x)->g4.add(i)); StepDetector.reset();
      walk(0,5,1.6,4f); walk(5,9,3.2,4f); StepDetector.setListener(null);
      int quick=0; for(int i=g4.size()-6;i<g4.size();i++) if(Math.abs(g4.get(i)-0.3125)<0.05) quick++;
      check(quick==6,"doubling the pace is followed: last gaps "+g4.subList(g4.size()-6,g4.size())); }
    // landing strength: once a stomp's bump is over, its own strength is told (before the hi-hat plays)
    { List<Float> land=new ArrayList<>(); StepDetector.setLandingListener(land::add); StepDetector.reset();
      walk(0,6,1.8,4f); float usual=land.get(land.size()-1); land.clear();
      double t0=6; walk(t0,t0+0.56,1.8,7f); float stomp=land.get(0); StepDetector.setLandingListener(null);
      check(Math.abs(usual-0.5f)<0.08f&&stomp>0.8f,"landing strength: usual "+usual+", the stomp itself "+stomp); }
    // sureness: uneven steps lower it, even ones bring it back
    { StepDetector.setListener(null); StepDetector.reset(); walk(0,6,1.8,4f); float even=StepDetector.sureness();
      double t=6; double[] gaps2={0.9,0.5,1.0,0.45}; for(double g:gaps2){ for(double u=0;u<g;u+=0.005) StepDetector.onAcceleration(0,0,9.80665f+(u<0.06?4f:0f),t+u); t+=g; }
      float uneven=StepDetector.sureness(); walk(t,t+5,1.8,4f); float back=StepDetector.sureness();
      check(even==1f&&uneven<0.6f&&back==1f,"rhythm sureness: even "+even+", uneven "+uneven+", settled again "+back); }
    // ---- selector ----
    WorldSelector s=new WorldSelector(); Set<String> all=new HashSet<>(Arrays.asList(WorldSelector.PRIORITY));
    String w=null; for(int i=0;i<300;i++) w=s.update(0.1,-40f,false,12*60,all);
    check(w==null,"middling room in daytime: no world");
    for(int i=0;i<30;i++) w=s.update(0.1,-60f,false,12*60,all);
    check(w==null,"quiet for 3 s is not enough (needs about 5 s and the average to settle)");
    for(int i=0;i<300;i++) w=s.update(0.1,-60f,false,12*60,all);
    check("tranquil".equals(w),"quiet room for a while -> tranquil: "+w);
    for(int i=0;i<10;i++) w=s.update(0.1,-10f,false,12*60,all);
    check("tranquil".equals(w),"a short loud burst does not change the world");
    for(int i=0;i<400;i++) w=s.update(0.1,-10f,false,12*60,all);
    check(w==null,"a steady roar (running water, a fan) is not flux: "+w);
    for(int i=0;i<400;i++) w=s.update(0.1,(i%5<2?-6f:-16f),false,12*60,all);
    check("flux".equals(w),"lively loud room for a while -> flux: "+w);
    for(int i=0;i<400;i++) w=s.update(0.1,-10f,true,12*60,all);
    check("kinetic".equals(w),"walking beats loud -> kinetic: "+w);
    for(int i=0;i<400;i++) w=s.update(0.1,-10f,true,60,all);
    check("ghost".equals(w),"1 AM beats everything -> ghost: "+w);
    for(int i=0;i<400;i++) w=s.update(0.1,-40f,false,12*60,all);
    check(w==null,"back to nothing when the situation ends: "+w);
    Set<String> noGhost=new HashSet<>(all); noGhost.remove("ghost");
    for(int i=0;i<400;i++) w=s.update(0.1,-40f,false,60,noGhost);
    check(w==null,"a world set to Off is skipped");
    s.reset(); for(int i=0;i<400;i++) w=s.update(0.1,-100f,false,12*60,all);
    check(w==null,"no mic reading yet is not mistaken for silence");
    // hysteresis: level hovering at the loud edge doesn't flip-flop
    s.reset(); for(int i=0;i<400;i++) w=s.update(0.1,-20f,false,12*60,all); for(int i=0;i<400;i++) w=s.update(0.1,-29f,false,12*60,all); int changes=0; String prev=w;
    for(int i=0;i<1200;i++){ w=s.update(0.1,i%2==0?-27f:-31f,false,12*60,all); if(!Objects.equals(prev,w)){changes++;prev=w;} }
    check(changes==0,"level hovering between the thresholds causes no flicker: "+changes);
    // ---- controller ----
    Context ctx=new Context(new java.io.File("/tmp/wtest")); Worlds.load(ctx); Worlds.reset();
    check(!Worlds.isEnabled()&&"Tranquil world".equals(Worlds.presetName("tranquil")),"defaults: off, each world has its preset");
    for(Worlds.World wd:Worlds.ALL){ check(PresetManager.builtIn(wd.defaultPreset)!=null,"built-in preset exists: "+wd.defaultPreset); }
    for(String n:new String[]{"Tranquil world","Flux world","Kinetic world","Ghost world","Pocket world"}){ Map<String,Float> pr=PresetManager.builtIn(n); boolean ok=true; for(Param p:Params.ALL) if(p.inPreset){Float v=pr.get(p.id); if(v==null||Math.abs(p.clamp(v)-v)>1e-4) ok=false;} check(ok,n+" has valid values for every preset setting"); }
    ParamStore.set("wet",0.2f); ParamStore.set("reverb_mix",0f);
    Worlds.tick(0.033,-60f,false,12*60);
    check(ParamStore.get("wet")==0.2f,"auto worlds off: sliders untouched");
    Worlds.setEnabled(true); int notes[]={0}; Worlds.setListener(()->notes[0]++);
    for(int i=0;i<400;i++) Worlds.tick(0.033,-60f,false,12*60);
    check("tranquil".equals(Worlds.currentWorld()),"tranquil engaged");
    Map<String,Float> tp=PresetManager.builtIn("Tranquil world");
    check(Math.abs(ParamStore.get("reverb_mix")-tp.get("reverb_mix"))<1e-3&&Math.abs(ParamStore.get("wet")-tp.get("wet"))<1e-3,"sliders ended at the world's preset values (wet "+ParamStore.get("wet")+")");
    check(ParamStore.get("echo_movers")==ParamStore.get("echo_movers")&&ParamStore.get(Params.moversSwitchId("space"))==1f,"world's movers switched on");
    check(notes[0]>=2,"screen was told about the change and the fade: "+notes[0]);
    // fade is gradual
    // hold: the world stays while the room changes, and follows the room again once let go
    Worlds.setHeld(true); for(int i=0;i<400;i++) Worlds.tick(0.033,-60f,true,12*60);
    check("tranquil".equals(Worlds.currentWorld())&&Worlds.isHeld(),"held: tranquil stays while walking ("+Worlds.currentWorld()+")");
    Worlds.setHeld(false); for(int i=0;i<100;i++) Worlds.tick(0.033,-60f,true,12*60);
    check("kinetic".equals(Worlds.currentWorld()),"let go: walking picks kinetic ("+Worlds.currentWorld()+")");
    Worlds.setHeld(true); Worlds.reset(); check(!Worlds.isHeld(),"a stop lets go of the hold");
    Worlds.setEnabled(true); for(int i=0;i<400;i++) Worlds.tick(0.033,-60f,false,12*60);
    Worlds.setEnabled(false); for(int i=0;i<200;i++) Worlds.tick(0.033,-60f,false,12*60);
    check(Math.abs(ParamStore.get("wet")-0.2f)<1e-3&&ParamStore.get("reverb_mix")==0f&&Worlds.currentWorld()==null,"switching auto worlds off fades the user's settings back");
    Worlds.setEnabled(true); Worlds.reset();
    for(int i=0;i<400;i++) Worlds.tick(0.033,-60f,false,12*60);
    ParamStore.setLocked("reverb_mix",true); float before=ParamStore.get("reverb_mix");
    for(int i=0;i<400;i++) Worlds.tick(0.033,(i%5<2?-6f:-16f),false,12*60);   // -> flux
    check("flux".equals(Worlds.currentWorld())&&ParamStore.get("reverb_mix")==before,"locked slider is left alone while the world changes");
    ParamStore.setLocked("reverb_mix",false);
    // midway through a fade values are between
    Worlds.reset(); Worlds.setEnabled(false); Worlds.setEnabled(true); ParamStore.set("wet",0.2f);
    for(int i=0;i<200;i++) Worlds.tick(0.033,-60f,false,12*60);
    ParamStore.set("wet",0.2f);
    // the "... enabled" switches belong to the user: worlds never flip them
    Worlds.setEnabled(false); for(int i=0;i<200;i++) Worlds.tick(0.033,-60f,false,12*60);
    Worlds.setPreset("flux","Flux world"); Worlds.setEnabled(true); Worlds.reset();
    ParamStore.set("crush_on",0f); ParamStore.set("ring_on",0f); ParamStore.set("crush_mix",0f);
    for(int i=0;i<600;i++) Worlds.tick(0.033,(i%5<2?-6f:-16f),false,12*60);
    check("flux".equals(Worlds.currentWorld())&&ParamStore.get("crush_mix")>0.1f,"flux world is playing (crush mix "+ParamStore.get("crush_mix")+")");
    check(ParamStore.get("crush_on")==0f&&ParamStore.get("ring_on")==0f,"switched-off effects stay switched off in a world");
    Worlds.reset();
    // stop restores home
    Worlds.reset();
    check(Worlds.currentWorld()==null,"reset leaves no world");
    // world set to Off is never used
    Worlds.setPreset("tranquil",Worlds.NONE); Worlds.reset(); ParamStore.set("wet",0.33f);
    for(int i=0;i<600;i++) Worlds.tick(0.033,-60f,false,12*60);
    check(Worlds.currentWorld()==null&&ParamStore.get("wet")==0.33f,"a world set to Off never plays");
    Worlds.setPreset("tranquil","No such preset"); for(int i=0;i<600;i++) Worlds.tick(0.033,-60f,false,12*60);
    check(ParamStore.get("wet")==0.33f,"a missing preset changes nothing");
    Worlds.setPreset("tranquil","Tranquil world");
    // stop mid-world restores the user's settings
    Worlds.setEnabled(true); Worlds.reset(); ParamStore.set("wet",0.33f); ParamStore.set("reverb_mix",0.1f);
    for(int i=0;i<400;i++) Worlds.tick(0.033,-60f,false,12*60);
    check(ParamStore.get("wet")!=0.33f,"world changed wet");
    Worlds.reset();
    check(Math.abs(ParamStore.get("wet")-0.33f)<1e-6&&Math.abs(ParamStore.get("reverb_mix")-0.1f)<1e-6,"stopping the engine hands the user's own settings back at once");
    System.out.println(fails==0?"ALL PASSED":(fails+" FAILED")); System.exit(fails==0?0:1);
  }
}
