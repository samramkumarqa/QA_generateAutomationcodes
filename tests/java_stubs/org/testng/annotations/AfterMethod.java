package org.testng.annotations;
import java.lang.annotation.*;
@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.METHOD) public @interface AfterMethod { boolean alwaysRun() default false; }
