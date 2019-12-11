from django.db import models

# Create your models here.
from meiduo_mall.utils.models import BaseModel



class OAuthQQUser(BaseModel):

    # 用户(外键)
    user = models.ForeignKey('users.User',
                             on_delete=models.CASCADE,
                             verbose_name='用户')
    # openid
    openid = models.CharField(max_length=64,
                              verbose_name='openid',
                              db_index=True)

    class Meta:
        db_table = 'tb_oauth_qq'
        verbose_name = 'qq的登录用户'
        verbose_name_plural = verbose_name