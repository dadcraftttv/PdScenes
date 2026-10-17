package org.puredata.core;
import java.util.*;
public class PdBase { public static final List<String> sent=new ArrayList<>(); public static int sendList(String r,Object... a){ sent.add(r+" list "+Arrays.toString(a)); return 0; } public static int sendFloat(String r,float x){ sent.add(r+"="+x); return 0; } public static int sendBang(String r){ sent.add(r+" bang"); return 0; } public static int sendMessage(String r,String m,Object... a){ sent.add(r+" "+m+" "+Arrays.toString(a)); return 0; } }
