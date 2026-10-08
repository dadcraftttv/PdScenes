package android.view;
public class MotionEvent { public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5,ACTION_POINTER_UP=6;
 public int action, actionIndex; public int[] ids; public float[] xs, ys;
 public MotionEvent(int action,int actionIndex,int[] ids,float[] xs,float[] ys){this.action=action;this.actionIndex=actionIndex;this.ids=ids;this.xs=xs;this.ys=ys;}
 public int getActionMasked(){return action;} public int getActionIndex(){return actionIndex;} public int getPointerCount(){return ids.length;}
 public int getPointerId(int i){return ids[i];} public float getX(int i){return xs[i];} public float getY(int i){return ys[i];} }
