package app.pdscenes;
import java.util.Random;
public class H {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static double t=0; static Random r=new Random(5);
  static float maxLevel; static int jolts;
  // 200 readings a second: gravity on z plus a jitter of size j (each reading), optional extra bumps
  static void run(double secs,float jitter,boolean walking,java.util.function.DoubleFunction<float[]> extra){
    maxLevel=0; jolts=0; double t0=t;
    for(double end=t+secs;t<end;t+=0.005){
      float[] e=extra==null?new float[3]:extra.apply(t-t0);   // (each stretch starts from rest)
      boolean j=HandlingDetector.onAcceleration(e[0]+jitter*(float)r.nextGaussian()/1.7f,e[1]+jitter*(float)r.nextGaussian()/1.7f,9.81f+e[2]+jitter*(float)r.nextGaussian()/1.7f,t,walking);
      if(j) jolts++;
      maxLevel=Math.max(maxLevel,HandlingDetector.level());
    }
  }
  public static void main(String[] a){
    HandlingDetector.reset();
    run(2,0f,false,null); run(2,0.003f,false,null);
    check(maxLevel==0 && jolts==0,"flat on a table: nothing ("+maxLevel+")");
    run(2,0.1f,false,null);
    check(maxLevel<0.05 && jolts==0,"held still: nothing ("+maxLevel+")");
    // walking with it in hand: a smooth 1.8 Hz sway of +-3 m/s^2 plus jitter peaking near 0.9
    run(5,0.35f,true,tt->new float[]{0,(float)(3*Math.sin(2*Math.PI*1.8*tt)),(float)(2*Math.sin(2*Math.PI*3.6*tt))});
    check(jolts==0 && maxLevel<0.05,"walking with it in hand: no jolts, no handling ("+jolts+", "+maxLevel+")");
    // finger taps: one sharp spike a second (a 5 m/s^2 jump for two readings)
    run(5,0.1f,false,tt->{double ph=tt%1.0; return new float[]{0,0,ph<0.01?5f:0f};});
    check(jolts==5 && maxLevel>0.95,"taps: one jolt each ("+jolts+"), handling at once ("+maxLevel+")");
    run(1,0.1f,false,null);
    check(HandlingDetector.level()<0.1,"...gone a second later ("+HandlingDetector.level()+")");
    // a tap while walking still counts
    run(3,0.35f,true,tt->{double ph=tt%1.0; return new float[]{0,(float)(3*Math.sin(2*Math.PI*1.8*tt))+(ph<0.01?6f:0f),0};});
    check(jolts==3,"taps while walking: still jolts ("+jolts+")");
    // rubbing: steady jitter peaking around 1.5, not walking -> handling; the same while walking -> nothing
    run(3,0.75f,false,null); float rub=maxLevel;
    run(1,0.1f,false,null);
    run(3,0.75f,true,null); float rubWalk=maxLevel;
    check(rub>0.4 && jolts==0 && rubWalk<0.05,"rubbing: handling "+rub+" standing, "+rubWalk+" walking, no jolts");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
