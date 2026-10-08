package android.view; import android.content.Context; import android.graphics.Canvas;
public class View { public int w,h,mw,mh; public View(Context c){} public int getWidth(){return w;} public int getHeight(){return h;} public void requestLayout(){} public void invalidate(){} public android.content.res.Resources getResources(){ return new android.content.res.Resources(); }
 public ViewParent getParent(){ return b->{}; }
 public static class MeasureSpec { public static int getSize(int s){return s;} }
 protected void onMeasure(int a,int b){} protected void onDraw(Canvas c){} public boolean onTouchEvent(MotionEvent e){return false;} protected void setMeasuredDimension(int a,int b){mw=a;mh=b;} }
