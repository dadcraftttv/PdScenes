package app.pdscenes;
import java.util.*;
public class M {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static Map<String,List<Float>> sent=new HashMap<>();
  static void run(double seconds,double dt){ for(double t=0;t<seconds;t+=dt) Modulation.tick(dt,(id,v)->sent.computeIfAbsent(id,k->new ArrayList<>()).add(v)); }
  static void setMover(String target,int shape,float speed,float depth){
    ParamStore.set(Params.moversSwitchId(Params.byId(target).section),1);
    ParamStore.set(Params.moverId(target,"mv"),shape); ParamStore.set(Params.moverId(target,"mvspeed"),speed); ParamStore.set(Params.moverId(target,"mvdepth"),depth); }
  static void off(String target){ ParamStore.set(Params.moverId(target,"mv"),0); }
  static float min(List<Float> l){ float m=1e9f; for(float f:l) m=Math.min(m,f); return m; }
  static float max(List<Float> l){ float m=-1e9f; for(float f:l) m=Math.max(m,f); return m; }
  public static void main(String[] a) throws Exception {
    // every movable slider has movement/speed/depth params and its section a switch
    for(Param p:Params.MOVABLE){ check(!p.toggle&&p.sendToPd&&p.choices==null,p.id+" movable is a Pd slider");
      Param mv=Params.byId(Params.moverId(p.id,"mv")); check(mv!=null&&mv.choices.length==16&&mv.section.equals(p.section)&&Params.byId(Params.moverId(p.id,"mvspeed"))!=null&&Params.byId(Params.moverId(p.id,"mvdepth"))!=null&&Params.byId(Params.moversSwitchId(p.section))!=null,p.id+" has mover params + section switch"); }
    check(Params.MOVABLE.size()>=38,"at least the 38 old targets are movable: "+Params.MOVABLE.size());
    check(Params.byId("mover1_target")==null,"old shared movers gone");
    Modulation.reset(); run(1,0.033); check(sent.isEmpty(),"movers off: nothing sent");
    ParamStore.set("wet",0.4f); Param wet=Params.byId("wet");
    float span=wet.toNorm(wet.randMax)-wet.toNorm(wet.randMin);
    // switch off by default even when a mover is chosen
    ParamStore.set(Params.moverId("wet","mv"),1); ParamStore.set(Params.moverId("wet","mvdepth"),0.5f); Modulation.reset(); run(1,0.033);
    check(sent.isEmpty(),"section switch off: chosen mover does nothing");
    ParamStore.set(Params.moversSwitchId("echo"),1); Modulation.reset(); sent.clear(); run(4,0.033);
    List<Float> w=sent.get("wet");
    check(w!=null && Math.abs(max(w)-(0.4f+0.5f*span*wet.max))<0.03 && Math.abs(min(w)-(0.4f-0.5f*span*wet.max))<0.03,"sine swings +-depth*range: "+min(w)+".."+max(w));
    // switching the section off restores base
    ParamStore.set(Params.moversSwitchId("echo"),0); sent.clear(); run(0.1,0.033);
    check(Math.abs(sent.get("wet").get(0)-0.4f)<1e-6,"switch off restores slider value");
    sent.clear(); run(0.5,0.033); check(sent.isEmpty(),"then nothing more sent");
    // other section unaffected: a mover in 'pitch' while echo switch is off
    setMover("pitch_semi",2,0.5f,0.5f); ParamStore.set(Params.moversSwitchId("echo"),0); Modulation.reset(); sent.clear(); run(5,0.033);
    check(sent.containsKey("pitch_semi")&&!sent.containsKey("wet"),"movers are per section: "+sent.keySet());
    // two sliders in the same section move independently
    setMover("wet",1,0.5f,0.5f); setMover("feedback",2,0.5f,0.5f); Modulation.reset(); sent.clear(); run(2,0.033);
    check(sent.containsKey("wet")&&sent.containsKey("feedback"),"two sliders in one section both move");
    off("wet"); off("feedback"); sent.clear(); run(0.1,0.033);
    check(Math.abs(sent.get("wet").get(0)-0.4f)<1e-6,"movement Off restores base");
    // depth 0
    ParamStore.set("wet",0.4f); setMover("wet",1,0.5f,0f); sent.clear(); run(1,0.033); check(max(sent.get("wet"))-min(sent.get("wet"))<1e-5,"depth 0 = no movement");
    // clamp
    ParamStore.set("feedback",0.85f); setMover("feedback",1,1f,1f); sent.clear(); Modulation.reset(); run(3,0.01);
    check(max(sent.get("feedback"))<=0.85f+1e-4 && min(sent.get("feedback"))>=-1e-4,"output stays in range");
    // drift
    ParamStore.set("pitch_semi",0f); Param ps=Params.byId("pitch_semi"); setMover("pitch_semi",2,0.5f,0.5f); sent.clear(); Modulation.reset(); run(60,0.033);
    List<Float> d=sent.get("pitch_semi"); float lim=0.5f*(ps.toNorm(ps.randMax)-ps.toNorm(ps.randMin))*(ps.max-ps.min);
    check(max(d)<=lim+1e-3 && min(d)>=-lim-1e-3 && max(d)-min(d)>lim*0.5f,"drift within bounds");
    // random jump (shape 12): holds, then hops >= 0.5 of the span; ~speed hops a second; stays in bounds
    ParamStore.set("wet",0.4f); setMover("wet",12,2f,0.5f); sent.clear(); Modulation.reset(); run(30,0.033);
    List<Float> j=sent.get("wet"); int hops=0; float minHop=9e9f, maxV=-9e9f, minV=9e9f; float swingJ=0.5f*span*wet.max;
    for(int i=1;i<j.size();i++){ float dv=Math.abs(j.get(i)-j.get(i-1)); if(dv>1e-6){hops++; minHop=Math.min(minHop,dv);} }
    for(float v:j){maxV=Math.max(maxV,v);minV=Math.min(minV,v);}
    check(hops>=50&&hops<=65,"random jump at 2 Hz hops about 60 times in 30 s: "+hops);
    check(minHop>=0.5f*swingJ*0.99f,"every hop is a clear move (smallest "+minHop+" of swing "+swingJ+")");
    check(maxV<=0.4f+swingJ+1e-3&&minV>=0.4f-swingJ-1e-3,"jumps stay within +-depth*range");
    // slider change goes through the offset while running
    off("pitch_semi"); setMover("wet",1,0.5f,0.5f); ParamStore.set("wet",0.4f); Modulation.reset(); run(0.6,0.033);
    org.puredata.core.PdBase.sent.clear(); AudioService.running=true; ParamStore.set("wet",0.5f);
    float sentV=Float.parseFloat(org.puredata.core.PdBase.sent.get(0).split("=")[1]);
    check(Math.abs(sentV-Modulation.output(wet,0.5f))<1e-6 && Math.abs(sentV-0.5f)>0.01f,"slider change sent through the offset");
    off("wet");
    // mic level shapes (3 higher, 4 lower)
    ParamStore.set("wet",0.4f); setMover("wet",3,1f,0.5f); Modulation.reset(); sent.clear();
    Modulation.setMicLevelDb(-100f); run(1,0.033); check(Math.abs(max(sent.get("wet"))-0.4f)<1e-4,"quiet room: no movement");
    Modulation.setMicLevelDb(-15f); sent.clear(); run(3,0.033); List<Float> ml=sent.get("wet");
    check(Math.abs(ml.get(ml.size()-1)-(0.4f+0.5f*span*wet.max))<0.01f,"loud pushes up");
    setMover("wet",4,1f,0.5f); Modulation.reset(); Modulation.setMicLevelDb(-15f); sent.clear(); run(3,0.033); ml=sent.get("wet");
    check(Math.abs(ml.get(ml.size()-1)-(0.4f-0.5f*span*wet.max))<0.01f,"louder = lower pushes down");
    Modulation.setMicLevelDb(-100f); off("wet"); run(0.1,0.033);
    // presets
    for(String n:PresetManager.builtInNames()){ Map<String,Float> pr=PresetManager.builtIn(n); for(Param p:Params.ALL) if(p.inPreset) { Float v=pr.get(p.id); if(v==null||Math.abs(p.clamp(v)-v)>1e-4) check(false,n+": bad/missing "+p.id+"="+v);} }
    ParamStore.applyPreset(PresetManager.builtIn("Wobbly pitch"));
    check(ParamStore.get(Params.moverId("pitch_semi","mv"))==1f&&ParamStore.get(Params.moversSwitchId("pitch"))==1f,"Wobbly pitch: pitch mover on, section switch on");
    Map<String,Float> old=new HashMap<>(); old.put("wet",0.2f); ParamStore.applyPreset(old);
    check(ParamStore.get(Params.moverId("pitch_semi","mv"))==0f&&ParamStore.get(Params.moversSwitchId("pitch"))==0f&&ParamStore.get("wet")==0.2f,"preset without movers switches them off");
    ParamStore.undo(); check(ParamStore.get(Params.moverId("pitch_semi","mv"))==1f,"undo restores movers");
    float mt=ParamStore.get(Params.moverId("pitch_semi","mv")); for(int i=0;i<200;i++){ParamStore.randomize();ParamStore.nudge(0.1f);}
    check(ParamStore.get(Params.moverId("pitch_semi","mv"))==mt&&ParamStore.get(Params.moversSwitchId("pitch"))==1f,"randomize/nudge leave movers alone");
    String js=PresetManager.toJson("x",ParamStore.snapshot()); check(js.contains("pitch_semi_mv")&&js.contains("pitch_movers"),"preset JSON includes movers");
    // legacy conversion: old mover1 -> echo wet (target 4), old shape 2 (louder=higher), mover2 -> pitch_semi (7) smooth
    org.json.JSONObject o=new org.json.JSONObject();
    o.put("mover1_target",4); o.put("mover1_shape",2); o.put("mover1_speed",0.7); o.put("mover1_depth",0.6);
    o.put("mover2_target",7); o.put("mover2_shape",0); o.put("mover2_speed",0.3); o.put("mover2_depth",0.2);
    o.put("mover3_target",0);
    Params.upgradeLegacyMovers(o);
    check(o.getDouble("wet_mv")==3&&Math.abs(o.getDouble("wet_mvspeed")-0.7)<1e-9&&Math.abs(o.getDouble("wet_mvdepth")-0.6)<1e-9&&o.getInt("echo_movers")==1,"legacy mover1 -> wet 'Louder = higher'");
    check(o.getDouble("pitch_semi_mv")==1&&o.getInt("pitch_movers")==1,"legacy mover2 -> pitch smooth wave");
    org.json.JSONObject none=new org.json.JSONObject(); none.put("wet",0.3); Params.upgradeLegacyMovers(none); check(!none.has("echo_movers"),"no legacy movers: nothing added");
    System.out.println(fails==0?"ALL PASSED":(fails+" FAILED")); System.exit(fails==0?0:1);
  }
}
