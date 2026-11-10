package org.openqa.selenium.remote;
import org.openqa.selenium.*; import java.util.List;
public class RemoteWebDriver implements WebDriver, TakesScreenshot {
  public void get(String u){} public String getCurrentUrl(){return null;} public void quit(){} public Options manage(){return null;}
  public List<WebElement> findElements(By b){return null;} public WebElement findElement(By b){return null;}
  public <X> X getScreenshotAs(OutputType<X> t){return null;} }
