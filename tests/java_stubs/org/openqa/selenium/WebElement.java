package org.openqa.selenium;
public interface WebElement extends SearchContext, TakesScreenshot {
  void click(); void clear(); void sendKeys(CharSequence... keys); boolean isSelected(); boolean isDisplayed();
  String getText(); String getDomProperty(String name); String getAttribute(String name); String getTagName(); }
