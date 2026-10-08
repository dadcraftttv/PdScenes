package app.pdscenes;
import java.util.*;
public class N {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static Map<String,List<Float>> sent=new HashMap<>();
  static void run(double seconds,double dt){ for(double t=0;t<seconds;t+=dt) Modulation.tick(dt,(id,v)->sent.computeIfAbsent(id,k->new ArrayList<>()).add(v)); }
  static void setMover(String target,int shape,float speed,float depth){
    ParamStore.set(Params.moversSwitchId(Params.byId(target).section),1);
    ParamStore.set(Params.moverId(target,"mv"),shape+1); ParamStore.set(Params.moverId(target,"mvspeed"),speed); ParamStore.set(Params.moverId(target,"mvdepth"),depth); }
  static float last(String id){ List<Float> l=sent.get(id); return l.get(l.size()-1); }
  public static void main(String[] a){
    Param wet=Params.byId("wet"); ParamStore.set("wet",0.4f);
    String WET="wet";
    float span=wet.toNorm(wet.randMax)-wet.toNorm(wet.randMin);
    float swing=0.5f*span*wet.max;   // depth 0.5
    String[] names=Params.MOVER_SHAPES;
    check(names.length==16 && names[4].equals("Louder = lower") && names[5].equals("Upright = higher"),"shape list extended at the end: "+names.length);
    // upright: flat = lowest, standing = highest
    setMover(WET,4,1f,0.5f); Modulation.reset();
    Modulation.onAcceleration(0,0,9.8f); sent.clear(); run(2,0.033); float flat=last("wet");
    Modulation.onAcceleration(0,9.8f,0); sent.clear(); run(2,0.033); float up=last("wet");
    check(up>flat+swing && Math.abs(up-(0.4f+swing))<0.01 && Math.abs(flat-(0.4f-swing))<0.01,"upright mover: flat "+flat+" standing "+up);
    // lean right: right edge down reads x = -g
    setMover(WET,5,1f,0.5f); Modulation.reset();
    Modulation.onAcceleration(-6.9f,0,6.9f); sent.clear(); run(2,0.033); float right=last("wet");
    Modulation.onAcceleration(6.9f,0,6.9f); sent.clear(); run(2,0.033); float left=last("wet");
    check(right>0.4f+swing*0.95f && left<0.4f-swing*0.95f,"lean mover: right "+right+" left "+left);
    // shake: quiet at rest, jumps on a jolt, fades back
    setMover(WET,6,1f,0.5f); Modulation.reset();
    Modulation.onAcceleration(0,0,9.80665f); sent.clear(); run(1,0.033); float still=last("wet");
    Modulation.onAcceleration(0,0,9.80665f*2.5f); sent.clear(); run(0.3,0.033); float shaken=last("wet");
    Modulation.onAcceleration(0,0,9.80665f); sent.clear(); run(4,0.033); float after=last("wet");
    check(Math.abs(still-0.4f)<0.005f && shaken>0.4f+swing*0.5f && Math.abs(after-0.4f)<0.01f,"shake mover: rest "+still+" shaken "+shaken+" later "+after);
    // spin
    setMover(WET,7,1f,0.5f); Modulation.reset();
    Modulation.onGyro(0,0,0); sent.clear(); run(1,0.033); float calm=last("wet");
    Modulation.onGyro(0,6,0); sent.clear(); run(2,0.033); float spinning=last("wet");
    check(Math.abs(calm-0.4f)<0.005f && Math.abs(spinning-(0.4f+swing))<0.01f,"spin mover: "+calm+" -> "+spinning);
    // heading: north low, south high
    setMover(WET,8,1f,0.5f); Modulation.reset();
    Modulation.onCompass(0); sent.clear(); run(2,0.033); float n=last("wet");
    Modulation.onCompass(180); sent.clear(); run(2,0.033); float s=last("wet");
    Modulation.onCompass(90); sent.clear(); run(2,0.033); float e=last("wet");
    check(Math.abs(n-(0.4f-swing))<0.01f && Math.abs(s-(0.4f+swing))<0.01f && Math.abs(e-0.4f)<0.01f,"heading mover: N "+n+" S "+s+" E "+e);
    // pad X / Y hold their last position
    setMover(WET,9,1f,0.5f); Modulation.reset();
    Modulation.onPad(1f,0.5f); sent.clear(); run(2,0.033); float px=last("wet");
    sent.clear(); run(3,0.033); float held=last("wet");
    setMover(WET,10,1f,0.5f); Modulation.reset(); Modulation.onPad(0.5f,0f); sent.clear(); run(2,0.033); float py=last("wet");
    check(Math.abs(px-(0.4f+swing))<0.01f && Math.abs(held-px)<1e-4f && Math.abs(py-(0.4f+swing))<0.01f,"pad movers: X right "+px+" held "+held+" Y top "+py);
    // slow speed reacts slowly
    setMover(WET,9,0.05f,0.5f); Modulation.reset(); Modulation.onPad(1f,0.5f); sent.clear(); run(0.5,0.033); float slow=last("wet");
    check(slow<0.4f+swing*0.6f && slow>0.4f,"low speed eases in gradually: "+slow);
    // output stays within range whatever the sensors say
    setMover(WET,6,2f,1f); Modulation.reset(); Modulation.onAcceleration(0,0,200f); sent.clear(); run(1,0.033);
    check(sent.get("wet").stream().allMatch(v->v>=0f&&v<=wet.max+1e-4),"extreme input stays within the parameter range");
    System.out.println(fails==0?"ALL PASSED":fails+" FAILED"); System.exit(fails==0?0:1);
  }
}
