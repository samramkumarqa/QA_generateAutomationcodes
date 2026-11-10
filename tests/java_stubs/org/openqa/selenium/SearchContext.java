package org.openqa.selenium;
import java.util.List;
public interface SearchContext { List<WebElement> findElements(By by); WebElement findElement(By by); }
