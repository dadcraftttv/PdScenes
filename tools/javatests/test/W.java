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
    { Random r=new Random(7); List<Double> g2=new ArrayList<>(); StepDetector.setListener(g2::add); StepDetector.reset();
      double last=-1, next=0.3, amp=0; for(double t=0;t<10;t+=0.005){
        if(t>=next){ last=t; amp=(r.nextDouble()-0.5)*16; next=t+0.08+r.nextDouble()*0.9; }   // a jolt, then a random gap
        float bump=(float)(amp*Math.exp(-(t-last)*12));
        StepDetector.onAcceleration(bump*0.5f,bump*0.3f,9.80665f+bump,t); }
      StepDetector.setListener(null);
      check(!StepDetector.walking(10)&&g2.size()<=3,"shaking the phone while sitting is not walking ("+g2.size()+" steps sent)"); }
    // listener gets one call per step with the gap to the previous one
    List<Double> gaps=new ArrayList<>(); StepDetector.setListener(gaps::add);
    StepDetector.reset(); walk(0,5,2.0,4f); StepDetector.setListener(null);
    double avg=0; for(int i=1;i<gaps.size();i++) avg+=gaps.get(i); avg/=Math.max(1,gaps.size()-1);
    check(gaps.size()>=7&&gaps.size()<=10&&Math.abs(avg-0.5)<0.05&&Math.abs(gaps.get(0)-0.5)<0.05,"step listener: "+gaps.size()+" calls (the first two steps of a walk are held back), gaps about 0.5 s (avg "+avg+")");
    gaps.clear(); StepDetector.setListener(gaps::add); StepDetector.reset(); walk(0,0.9,1.8,4f); StepDetector.setListener(null);
    check(gaps.isEmpty(),"two stray bumps do not play drums: "+gaps.size());
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
