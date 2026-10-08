package org.json;
import java.util.*;
public class JSONObject {
  final Map<String,Object> m = new LinkedHashMap<>();
  public JSONObject(){}
  public JSONObject(String s) throws JSONException { P p=new P(s); Object o=p.val(); p.ws(); if(!(o instanceof JSONObject)||p.i!=s.length()) throw new JSONException("bad json"); m.putAll(((JSONObject)o).m); }
  public JSONObject put(String k,Object v) throws JSONException { m.put(k,v); return this; }
  public JSONObject put(String k,double v) throws JSONException { if(Double.isNaN(v)||Double.isInfinite(v)) throw new JSONException("nan"); m.put(k,v); return this; }
  public JSONObject put(String k,int v) throws JSONException { m.put(k,v); return this; }
  public double optDouble(String k,double d){ Object o=m.get(k); return o instanceof Number?((Number)o).doubleValue():d; }
  public int getInt(String k) throws JSONException { return (int)getDouble(k); }
  public boolean has(String k){ return m.containsKey(k); }
  public double getDouble(String k) throws JSONException { Object o=m.get(k); if(o instanceof Number) return ((Number)o).doubleValue(); throw new JSONException("not number: "+k); }
  public JSONObject getJSONObject(String k) throws JSONException { Object o=m.get(k); if(o instanceof JSONObject) return (JSONObject)o; throw new JSONException("not object: "+k); }
  public JSONObject optJSONObject(String k){ Object o=m.get(k); return o instanceof JSONObject?(JSONObject)o:null; }
  public JSONArray optJSONArray(String k){ Object o=m.get(k); return o instanceof JSONArray?(JSONArray)o:null; }
  public String optString(String k,String d){ Object o=m.get(k); return o instanceof String?(String)o:d; }
  public String toString(){ StringBuilder b=new StringBuilder("{"); boolean f=true; for(Map.Entry<String,Object> e:m.entrySet()){ if(!f)b.append(','); f=false; b.append(ser(e.getKey())).append(':').append(ser(e.getValue())); } return b.append('}').toString(); }
  public String toString(int indent){ return toString(); }
  static String ser(Object o){ if(o instanceof String) return "\""+((String)o).replace("\\","\\\\").replace("\"","\\\"")+"\""; return String.valueOf(o); }
  static class P { String s; int i=0; P(String s){this.s=s;}
    void ws(){ while(i<s.length()&&Character.isWhitespace(s.charAt(i))) i++; }
    Object val() throws JSONException { ws(); if(i>=s.length()) throw new JSONException("eof"); char c=s.charAt(i);
      if(c=='{'){ i++; JSONObject o=new JSONObject(); ws(); if(s.charAt(i)=='}'){i++;return o;} while(true){ ws(); String k=str(); ws(); if(s.charAt(i++)!=':') throw new JSONException(":"); o.m.put(k,val()); ws(); char d=s.charAt(i++); if(d=='}') return o; if(d!=',') throw new JSONException(","); } }
      if(c=='['){ i++; JSONArray a=new JSONArray(); ws(); if(s.charAt(i)==']'){i++;return a;} while(true){ a.put(val()); ws(); char d=s.charAt(i++); if(d==']') return a; if(d!=',') throw new JSONException(","); } }
      if(c=='"') return str();
      int j=i; while(i<s.length()&&"+-0123456789.eE".indexOf(s.charAt(i))>=0) i++; if(j==i) throw new JSONException("bad token"); return Double.parseDouble(s.substring(j,i)); }
    String str() throws JSONException { if(s.charAt(i)!='"') throw new JSONException("str"); i++; StringBuilder b=new StringBuilder(); while(s.charAt(i)!='"'){ char c=s.charAt(i++); if(c=='\\') c=s.charAt(i++); b.append(c);} i++; return b.toString(); } }
}
