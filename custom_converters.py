from discord.ext.commands import Converter, BadArgument


#---------------------------+
#        Exceptions         |
#---------------------------+
class IsNotInt(BadArgument):
    def __init__(self, argument):
        self.argument = argument
    
    def __str__(self):
        return f'int "{self.argument}" [custom]'


class IsNotFloat(BadArgument):
    def __init__(self, argument):
        self.argument = argument
    
    def __str__(self):
        return f'float "{self.argument}" [custom]'


#---------------------------+
#        Converters         |
#---------------------------+
class IntConverter(Converter):
    async def convert(self, ctx, argument):
        try:
            return int(argument)
        except:
            raise IsNotInt(argument)


class FloatConverter(Converter):
    async def convert(self, ctx, argument):
        try:
            return float(argument)
        except:
            raise IsNotFloat(argument)


# End