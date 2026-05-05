<?php

use Illuminate\Support\Facades\Route;

Route::get('/boom', function () {
    throw new RuntimeException('тест Laravel + Error Monitor SDK');
});