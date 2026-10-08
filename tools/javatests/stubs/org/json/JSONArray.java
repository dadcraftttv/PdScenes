package org.json;
import java.util.*;
public class JSONArray {
  final List<Object> l = new ArrayList<>();
  public JSONArray put(Object o){ l.add(o); return this; }
  public int length(){ return l.size(); }
  public String getString(int i) throws JSONException { Object o=l.get(i); if(!(o instanceof String)) throw new JSONException("not string"); return (String)o; }
  public String toString(){ StringBuilder b=new StringBuilder("["); for(int i=0;i<l.size();i++){ if(i>0)b.append(','); b.append(JSONObject.ser(l.get(i))); } return b.append(']').toString(); }
}
