package org.openqa.selenium;
import java.util.List; import java.time.Duration;
public interface WebDriver extends SearchContext {
  void get(String url); String getCurrentUrl(); void quit(); Options manage();
  interface Options { Timeouts timeouts(); }
  interface Timeouts { Timeouts pageLoadTimeout(Duration d); Timeouts implicitlyWait(Duration d); }
}
