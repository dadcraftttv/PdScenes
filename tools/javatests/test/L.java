package app.pdscenes;
import java.util.*;
public class L {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static String show(List<MotifMemory.Note> a){ if(a==null) return "null"; StringBuilder b=new StringBuilder(); for(MotifMemory.Note n:a) b.append(String.format("%.1f:%d ",n.at,n.degree)); return b.toString(); }
  public static void main(String[] a){
    CallResponse c=new CallResponse(new Random(3));
    c.onNote(0,10.0); c.onNoteOff(10.4); c.onNote(2,10.5); c.onNoteOff(10.9); c.onNote(4,11.0);
    check(c.poll(11.5,1f,7)==null,"nothing while a note is still sung");
    c.onNoteOff(11.6);
    check(c.poll(13.0,1f,7)==null,"nothing until the phrase has ended (1.6 s of quiet)");
    List<MotifMemory.Note> ans=c.poll(13.3,1f,7);
    check(ans!=null && ans.size()==3 && ans.get(0).at==0 && Math.abs(ans.get(1).at-0.5)<1e-9 && Math.abs(ans.get(2).at-1.0)<1e-9
        && ans.get(0).degree==2 && ans.get(1).degree==4 && (ans.get(2).degree==6 || ans.get(2).degree==7),
        "a three-note phrase is answered in its own rhythm, a third up (the last note may resolve to the key): "+show(ans));
    check(c.poll(14,1f,7)==null,"each phrase is answered once");
    c.onNote(15,20); c.onNoteOff(20.3); c.onNote(16,20.4); c.onNoteOff(20.8);
    ans=c.poll(22.5,1f,7);
    check(ans!=null && ans.get(0).degree==13,"a high phrase is answered a third below: "+show(ans));
    c.onNote(3,30); c.onNoteOff(30.4);
    check(c.poll(31.5,0f,7)==null,"Call and response at 0 answers nothing");
    c.onNote(3,40); c.onNoteOff(40.2);
    check(c.poll(42,1f,7)!=null,"one note is a phrase too (a hummed note gets its echo)");
    c.onNote(1,50); c.onNoteOff(50.1); c.onNote(5,52); c.onNoteOff(52.2);
    ans=c.poll(54,1f,7);
    check(ans!=null && ans.size()==1 && ans.get(0).degree==7,"a pause over 1.5 s starts a new phrase: only the last one is answered "+show(ans));
    for(int i=0;i<9;i++){ c.onNote(i,60+i*0.3); c.onNoteOff(60+i*0.3+0.2); }
    ans=c.poll(65,1f,7);
    check(ans!=null && ans.size()==6 && ans.get(0).degree==3+2,"a long phrase is answered with its last six notes "+show(ans));
    check(CallResponse.velocity(0.5f)<CallResponse.velocity(1f) && CallResponse.velocity(0)==0,"the setting sets how loud the answer is");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
