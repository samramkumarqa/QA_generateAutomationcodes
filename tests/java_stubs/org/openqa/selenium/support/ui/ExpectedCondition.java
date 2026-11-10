package org.openqa.selenium.support.ui;
import org.openqa.selenium.WebDriver; import java.util.function.Function;
public interface ExpectedCondition<T> extends Function<WebDriver, T> { }
