class Permission:
    PUBLIC = 1
    ALUMNI = 2
    MEMBER = 3
    MODERATOR = 4
    ADMIN = 5

    class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    permissions = db.Column(db.Integer)

        def __init__(self, name):
            self.name = name
            self.permissions = 0

        def add_permission(self, perm):
            if not self.has_permission(perm):
                self.permissions |= perm

        def remove_permission(self, perm):
            if self.has_permission(perm):
                self.permissions &= ~perm

        def reset_permissions(self):
            self.permissions = 0

        def has_permission(self, perm):
            return self.permissions & perm == perm

role_admin = Role('Admin')
role_admin.add_permission(Permission.ADMIN)
role_admin.add_permission(Permission.MODERATE)
role_admin.add_permission(Permission.PUBLISH)

role_moderator = Role('Moderator')
role_moderator.add_permission(Permission.MODERATE)
role_moderator.add_permission(Permission.COMMENT)
